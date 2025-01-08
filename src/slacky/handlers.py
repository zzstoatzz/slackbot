from typing import Any, Callable

import prefect.runtime.flow_run
from prefect import flow, get_run_logger, task

from .agent import get_agent
from .logging import get_logger
from .utils import (
    get_channel_name,
    is_positive_reaction,
    scrub_app_mention,
    send_slack_message,
)

logger = get_logger(__name__)


@task
async def run_agent(
    message: str,
    thread_ts: str,
    channel: str,
    tools: list[Callable[..., Any]] | None = None,
) -> str:
    """Run the agent and return the response."""
    # Clean the message before sending to agent
    cleaned_message = scrub_app_mention(message)
    return await get_agent(tools).handle_message(cleaned_message, thread_ts, channel)


def _generate_flow_run_name() -> str:
    parameters = prefect.runtime.flow_run.parameters
    channel_name = get_channel_name(parameters.get("channel"))
    return f"handle message in {channel_name}/{parameters.get('thread_ts')}"


@flow(
    name="handle slack message",
    flow_run_name=_generate_flow_run_name,
    description="Handle a Slack message in a thread",
)
async def handle_message(
    message: str,
    thread_ts: str,
    channel: str,
) -> None:
    """Process a Slack message in the background using Prefect."""
    logger = get_run_logger()
    logger.debug(f"Processing message from thread {thread_ts} in background: {message}")

    try:
        agent_response = await run_agent(
            message=message, thread_ts=thread_ts, channel=channel
        )

        logger.info(f"Generated response for 🧵 {thread_ts}")
        logger.info(f"🤖: {agent_response}")

        await send_slack_message(
            text=agent_response,
            thread_ts=thread_ts,
            channel=channel,
        )
    except Exception as e:
        logger.error(f"Error processing message in thread {thread_ts}: {e}")
        await send_slack_message(
            text="Sorry, I encountered an error while processing your message.",
            thread_ts=thread_ts,
            channel=channel,
        )


@task
async def handle_reaction(event: dict[str, Any]) -> None:
    """Handle a reaction event."""
    reaction = event.get("reaction")
    if not is_positive_reaction(reaction):
        return

    # For now, just log the reaction
    logger.info(
        f"Received {reaction} reaction from user {event.get('user')} "
        f"on message {event.get('item', {}).get('ts')} "
        f"in channel {event.get('item', {}).get('channel')}"
    )

    await send_slack_message(
        text=f"Feedback received: {reaction}",
        thread_ts=event.get("item", {}).get("ts"),
        channel=event.get("item", {}).get("channel"),
    )
