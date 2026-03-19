import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request
from uuid import uuid4

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
from starlette.concurrency import run_in_threadpool
import sqlparse
from sqlparse import tokens as T


load_dotenv()


MAX_SQL_CHARS = 50_000
MAX_REQUEST_BODY_BYTES = 200 * 1024
RAILWAY_HOST = "sql-query-formatter-production.up.railway.app"
CANONICAL_HOST = "sql-formatter.dev"
DEFAULT_ALLOWED_ORIGINS = "http://localhost:8000,http://127.0.0.1:8000,http://127.0.0.1:5500"
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_APP_ENV = "local"
FEEDBACK_WEBHOOK_TIMEOUT_SECONDS = 10

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

class FeedbackRequest(BaseModel):
    email: str = ""
    message: str

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Message cannot be empty.")
        if len(value) > 5_000:
            raise ValueError("Message too long (max 5000 characters).")
        return value

    @field_validator("email")
    @classmethod
    def validate_email_field(cls, value: str) -> str:
        value = value.strip()
        if value and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", value):
            raise ValueError("Invalid email address.")
        return value


def build_feedback_webhook_url(base_url: str, token: str) -> str:
    parsed_url = urllib_parse.urlparse(base_url)
    existing_query = urllib_parse.parse_qs(parsed_url.query, keep_blank_values=True)
    existing_query["token"] = [token]
    encoded_query = urllib_parse.urlencode(existing_query, doseq=True)
    return urllib_parse.urlunparse(parsed_url._replace(query=encoded_query))


def post_feedback_webhook(url: str, payload: dict) -> dict:
    request_body = json.dumps(payload).encode("utf-8")
    webhook_request = urllib_request.Request(
        url,
        data=request_body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    with urllib_request.urlopen(webhook_request, timeout=FEEDBACK_WEBHOOK_TIMEOUT_SECONDS) as response:
        response_status = getattr(response, "status", 200)
        response_body = response.read().decode("utf-8")
    if response_status < 200 or response_status >= 300:
        raise ValueError(f"Feedback webhook returned unexpected status {response_status}.")
    if not response_body:
        logger.warning("event=feedback_webhook_empty_response")
        return {
            "ok": True,
            "status": "accepted",
            "transport": "empty-response",
        }
    try:
        return json.loads(response_body)
    except json.JSONDecodeError:
        logger.warning(
            "event=feedback_webhook_non_json_response body_preview=%s",
            response_body[:160],
        )
        return {
            "ok": True,
            "status": "accepted",
            "transport": "non-json-response",
        }


limiter = Limiter(key_func=get_remote_address)
app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
INDEX_FILE = FRONTEND_DIR / "index.html"
PRIVACY_FILE = FRONTEND_DIR / "privacy.html"

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
    logger.info(
        "event=server_startup allowed_origins=%s feedback_webhook_configured=%s",
        allowed_origins,
        bool(os.getenv("FEEDBACK_WEBHOOK_URL") and os.getenv("FEEDBACK_WEBHOOK_TOKEN")),
    )


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


@app.get("/privacy")
async def privacy_page():
    return FileResponse(PRIVACY_FILE)


@app.get("/style.css")
async def style_file():
    return RedirectResponse(url="/static/style.css")


@app.get("/app.js")
async def script_file():
    return RedirectResponse(url="/static/app.js")


@app.get("/healthz")
async def health_check():
    return {"status": "ok"}


@app.post("/feedback")
@limiter.limit("10/minute")
async def submit_feedback(request: Request, payload: FeedbackRequest):
    feedback_webhook_url = os.getenv("FEEDBACK_WEBHOOK_URL", "").strip()
    feedback_webhook_token = os.getenv("FEEDBACK_WEBHOOK_TOKEN", "").strip()
    app_env = os.getenv("APP_ENV", DEFAULT_APP_ENV).strip() or DEFAULT_APP_ENV

    request_id = f"req_{uuid4().hex}"
    submitted_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    client_ip = get_remote_address(request)
    user_agent = request.headers.get("user-agent", "")
    from_label = payload.email if payload.email else "Anonymous"

    logger.info("event=feedback_received from=%s request_id=%s", from_label, request_id)

    if not feedback_webhook_url or not feedback_webhook_token:
        logger.warning("event=feedback_webhook_not_configured request_id=%s", request_id)
        return JSONResponse(
            status_code=503,
            content={
                "error": "FEEDBACK_NOT_CONFIGURED",
                "message": "Feedback storage is not configured on the server.",
            },
        )

    webhook_url = build_feedback_webhook_url(feedback_webhook_url, feedback_webhook_token)
    webhook_payload = {
        "version": "1.0",
        "submitted_at": submitted_at,
        "source": "web",
        "email": payload.email,
        "message": payload.message,
        "meta_ip": client_ip,
        "meta_user_agent": user_agent,
        "meta_env": app_env,
        "request_id": request_id,
    }

    try:
        webhook_response = await run_in_threadpool(post_feedback_webhook, webhook_url, webhook_payload)
        if webhook_response.get("ok") is not True or webhook_response.get("status") != "accepted":
            logger.warning(
                "event=feedback_webhook_rejected request_id=%s error_code=%s message=%s",
                request_id,
                webhook_response.get("error_code", "UNKNOWN"),
                webhook_response.get("message", "Unknown feedback webhook rejection."),
            )
            return JSONResponse(
                status_code=502,
                content={
                    "error": "FEEDBACK_DELIVERY_FAILED",
                    "message": webhook_response.get("message", "Feedback storage rejected the submission."),
                },
            )

        logger.info(
            "event=feedback_stored from=%s request_id=%s row_number=%s",
            from_label,
            request_id,
            webhook_response.get("row_number"),
        )
        return {"status": "ok"}
    except urllib_error.HTTPError as exc:
        logger.exception("event=feedback_webhook_http_error request_id=%s status=%s", request_id, exc.code)
        return JSONResponse(
            status_code=502,
            content={
                "error": "FEEDBACK_DELIVERY_FAILED",
                "message": "Feedback storage endpoint returned an error.",
            },
        )
    except (urllib_error.URLError, TimeoutError, ValueError):
        logger.exception("event=feedback_webhook_request_error request_id=%s", request_id)
        return JSONResponse(
            status_code=502,
            content={
                "error": "FEEDBACK_DELIVERY_FAILED",
                "message": "Failed to store feedback.",
            },
        )


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
