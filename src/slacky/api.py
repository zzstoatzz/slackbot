import asyncio
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from starlette.routing import Route

from .handlers import handle_message, handle_reaction
from .listener import listen_for_events
from .logging import get_logger
from .utils import verify_slack_request

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("=== Available routes ===")
    for route in app.routes:
        assert isinstance(route, Route), f"{route} is not a starlette.routing.Route"
        logger.info(
            f"Path: {route.path}, Methods: {route.methods}, Endpoint: {route.endpoint.__name__}"
        )

    asyncio.create_task(listen_for_events())
    yield


app = FastAPI(lifespan=lifespan)


class SlackEvent(BaseModel):
    type: str
    event: dict[str, Any] | None = None
    challenge: str | None = None


@app.post("/chat")
async def handle_slack_event(request: Request):
    logger.debug(f"Received request: {request.method} {request.url.path}")
    logger.debug(f"Headers: {request.headers}")
    if not await verify_slack_request(request):
        raise HTTPException(status_code=400, detail="Invalid request signature")

    body = await request.json()
    event = SlackEvent(**body)

    if event.type == "url_verification":
        return {"challenge": event.challenge}

    if event.type == "event_callback" and event.event:
        event_type = event.event.get("type")

        if event_type == "reaction_added":
            asyncio.ensure_future(handle_reaction(event.event))
            return {"ok": True}

        if event_type == "app_mention":
            channel = event.event.get("channel")
            thread_ts = event.event.get("thread_ts") or event.event.get("ts")
            text = event.event.get("text", "")

            assert thread_ts is not None, "thread_ts is required"
            assert channel is not None, "channel is required"

            logger.info(f"Backgrounding message processing for thread {thread_ts}")
            logger.debug(f"Message text: {text}")

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
