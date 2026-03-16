import logging
import os
import re
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator
from dotenv import load_dotenv
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
import sqlparse
from sqlparse import tokens as T


load_dotenv()


MAX_SQL_CHARS = 50_000
MAX_REQUEST_BODY_BYTES = 200 * 1024
RAILWAY_HOST = "sql-query-formatter-production.up.railway.app"
CANONICAL_HOST = "sql-formatter.dev"
DEFAULT_ALLOWED_ORIGINS = "http://localhost:8000,http://127.0.0.1:8000,http://127.0.0.1:5500"
DEFAULT_LOG_LEVEL = "INFO"

def resolve_log_level() -> int:
    configured_level = os.getenv("LOG_LEVEL", DEFAULT_LOG_LEVEL).upper()
    return getattr(logging, configured_level, logging.INFO)


logging.basicConfig(
    level=resolve_log_level(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("sql_formatter_api")

_VALID_FIRST_TTYPES = frozenset([T.Keyword.DML, T.Keyword.DDL, T.Keyword.CTE])


def looks_like_sql(sql: str) -> bool:
    stripped = sql.strip()
    if not stripped:
        return False
    if re.match(r"https?://|www\.", stripped, re.IGNORECASE):
        return False
    parsed = sqlparse.parse(stripped)
    if not parsed:
        return False
    stmt = parsed[0]
    first = None
    for tok in stmt.flatten():
        if tok.is_whitespace or tok.ttype in (T.Comment.Single, T.Comment.Multiline):
            continue
        first = tok
        break
    if first is None:
        return False
    return first.ttype in _VALID_FIRST_TTYPES


class FormatRequest(BaseModel):
    sql: str
    indent_size: int = 4
    keyword_case: str = "upper"
    dialect: str = "generic"

    @field_validator("sql")
    @classmethod
    def validate_sql(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("SQL input cannot be empty.")
        if len(normalized) > MAX_SQL_CHARS:
            raise ValueError(f"SQL exceeds maximum length of {MAX_SQL_CHARS} characters")
        return normalized

    @field_validator("indent_size")
    @classmethod
    def validate_indent_size(cls, value: int) -> int:
        if value not in (2, 4):
            raise ValueError("indent_size must be 2 or 4")
        return value

    @field_validator("keyword_case")
    @classmethod
    def validate_keyword_case(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in ("upper", "lower", "preserve"):
            raise ValueError("keyword_case must be upper, lower, or preserve")
        return normalized

    @field_validator("dialect")
    @classmethod
    def validate_dialect(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in ("generic", "postgres", "mysql", "spark"):
            raise ValueError("dialect must be generic, postgres, mysql, or spark")
        return normalized
limiter = Limiter(key_func=get_remote_address)
app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
INDEX_FILE = FRONTEND_DIR / "index.html"

allowed_origins = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", DEFAULT_ALLOWED_ORIGINS).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.middleware("http")
async def canonical_domain_redirect(request: Request, call_next):
    if request.url.hostname == RAILWAY_HOST:
        canonical_url = f"https://{CANONICAL_HOST}{request.url.path}"
        if request.url.query:
            canonical_url = f"{canonical_url}?{request.url.query}"
        return RedirectResponse(url=canonical_url, status_code=301)
    return await call_next(request)


@app.middleware("http")
async def request_size_guard(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_REQUEST_BODY_BYTES:
                return JSONResponse(
                    status_code=413,
                    content={
                        "error": "REQUEST_TOO_LARGE",
                        "message": "Request body too large",
                    },
                )
        except ValueError:
            # If content-length is malformed, continue and let FastAPI handle parsing.
            pass
    return await call_next(request)


@app.on_event("startup")
async def on_startup() -> None:
    logger.info("event=server_startup allowed_origins=%s", allowed_origins)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    first_error = exc.errors()[0] if exc.errors() else {}
    message = first_error.get("msg", "Invalid request body")
    logger.warning(
        "event=validation_error path=%s ip=%s message=%s",
        request.url.path,
        get_remote_address(request),
        message,
    )
    return JSONResponse(
        status_code=422,
        content={
            "error": "VALIDATION_ERROR",
            "message": message,
        },
    )


@app.get("/")
async def home_page():
    return FileResponse(INDEX_FILE)


@app.get("/style.css")
async def style_file():
    return RedirectResponse(url="/static/style.css")


@app.get("/app.js")
async def script_file():
    return RedirectResponse(url="/static/app.js")


@app.get("/healthz")
async def health_check():
    return {"status": "ok"}


@app.post("/format")
@limiter.limit("60/minute")
async def format_sql(request: Request, payload: FormatRequest):
    client_ip = get_remote_address(request)
    logger.info(
        "event=format_request ip=%s sql_length=%d indent_size=%d keyword_case=%s dialect=%s",
        client_ip,
        len(payload.sql),
        payload.indent_size,
        payload.keyword_case,
        payload.dialect,
    )

    if not looks_like_sql(payload.sql):
        logger.warning("event=invalid_sql_input ip=%s", client_ip)
        raise HTTPException(status_code=400, detail="Input does not appear to be valid SQL.")

    try:
        # Dialect is accepted for future rule sets; currently formatting behavior is shared.
        _dialect = payload.dialect
        formatted = sqlparse.format(
            payload.sql,
            reindent=True,
            indent_width=payload.indent_size,
            keyword_case=None if payload.keyword_case == "preserve" else payload.keyword_case,
        )
        return {"formatted": formatted}
    except Exception:
        logger.exception("event=format_error ip=%s", client_ip)
        return JSONResponse(
            status_code=500,
            content={
                "error": "FORMAT_ERROR",
                "message": "Unable to format SQL",
            },
        )
