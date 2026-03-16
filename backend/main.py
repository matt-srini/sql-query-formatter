import logging
import os
from pathlib import Path

from fastapi import FastAPI, Request
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


load_dotenv()


MAX_SQL_CHARS = 50_000
MAX_REQUEST_BODY_BYTES = 200 * 1024
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


class FormatRequest(BaseModel):
    sql: str

    @field_validator("sql")
    @classmethod
    def validate_sql(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("SQL must not be empty")
        if len(normalized) > MAX_SQL_CHARS:
            raise ValueError(f"SQL exceeds maximum length of {MAX_SQL_CHARS} characters")
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
        "event=format_request ip=%s sql_length=%d",
        client_ip,
        len(payload.sql),
    )

    try:
        formatted = sqlparse.format(payload.sql, reindent=True, keyword_case="upper")
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
