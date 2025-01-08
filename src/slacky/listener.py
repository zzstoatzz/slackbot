from prefect.events import get_events_subscriber
from prefect.events.filters import EventFilter

from .logging import get_logger

logger = get_logger(__name__)


async def listen_for_events(events_filter: EventFilter | None = None) -> None:
    """Listen for events and handle them."""
    async with get_events_subscriber(filter=events_filter) as subscriber:
        async for event in subscriber:
            logger.info(f"📥 event: {event.event}")
