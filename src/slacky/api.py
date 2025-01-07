import asyncio
import hashlib
import hmac
import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from starlette.routing import Route

from .handlers import handle_message
from .logging import get_logger
from .settings import settings

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=== Available routes ===")
    for route in app.routes:
        assert isinstance(route, Route), f"{route} is not a starlette.routing.Route"
        logger.info(
            f"Path: {route.path}, Methods: {route.methods}, Endpoint: {route.endpoint.__name__}"
        )
    yield


app = FastAPI(lifespan=lifespan)


class SlackEvent(BaseModel):
    type: str
    event: dict[str, Any] | None = None
    challenge: str | None = None


async def _verify_slack_request(request: Request) -> bool:
    """Verify that the request came from Slack"""
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")

    if abs(time.time() - int(timestamp)) > 60 * 5:
        return False

    body = await request.body()
    sig_basestring = f"v0:{timestamp}:{body.decode()}"
    my_signature = f"v0={hmac.new(settings.signing_secret.get_secret_value().encode(), sig_basestring.encode(), hashlib.sha256).hexdigest()}"

    verified = hmac.compare_digest(my_signature, signature)
    logger.debug(f"Signature verification: {verified}")
    return verified


@app.post("/chat")
async def handle_slack_event(request: Request):
    logger.debug(f"Received request: {request.method} {request.url.path}")
    logger.debug(f"Headers: {request.headers}")
    if not await _verify_slack_request(request):
        raise HTTPException(status_code=400, detail="Invalid request signature")

    body = await request.json()
    event = SlackEvent(**body)

    if event.type == "url_verification":
        return {"challenge": event.challenge}

    if event.type == "event_callback" and event.event:
        if event.event.get("type") == "app_mention":
            channel = event.event.get("channel")
            thread_ts = event.event.get("thread_ts") or event.event.get("ts")
            text = event.event.get("text", "")

            assert thread_ts is not None, "thread_ts is required"
            assert channel is not None, "channel is required"

            logger.info(f"Backgrounding message processing for thread {thread_ts}")
            logger.debug(f"Message text: {text}")

            # Process message in background
            asyncio.ensure_future(
                handle_message(
                    message=text,
                    thread_ts=thread_ts,
                    channel=channel,
                )
            )
            logger.info(f"Backgrounded message processing for thread {thread_ts}")

    return {"ok": True}


@app.get("/")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok"}
