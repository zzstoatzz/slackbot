import re
from typing import TypedDict, Unpack

import httpx
from prefect import flow, get_run_logger, task

from .agent import SlackAgent
from .settings import settings
from .tools import add_sitemap_to_knowledgebase, query_knowledgebase


class SlackMessage(TypedDict):
    """A Slack message to send to the API."""

    channel: str
    thread_ts: str
    text: str


# Initialize the agent with OpenAI model
agent = SlackAgent(
    model=settings.ai_model,
    system_prompt=settings.base_system_prompt,
    tools=[query_knowledgebase, add_sitemap_to_knowledgebase],
)


def _scrub_app_mention(message: str) -> str:
    """Remove app mention from the message."""
    # Remove any <@U...> mentions from the start of the message
    cleaned = re.sub(r"^\s*<@[A-Z0-9]+>\s*", "", message)
    return cleaned.strip()


@task
async def send_slack_message(**slack_message_kwargs: Unpack[SlackMessage]) -> None:
    """Send a message to Slack."""
    logger = get_run_logger()
    logger.info(f"Sending message to Slack: {slack_message_kwargs}")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://slack.com/api/chat.postMessage",
            headers={
                "Authorization": f"Bearer {settings.bot_token.get_secret_value()}"
            },
            json=slack_message_kwargs,
        )
        response.raise_for_status()


@task
async def run_agent(message: str, thread_ts: str, channel: str) -> str:
    """Run the agent and return the response."""
    # Clean the message before sending to agent
    cleaned_message = _scrub_app_mention(message)
    return await agent.handle_message(cleaned_message, thread_ts, channel)


@flow(
    name="handle slack message",
    flow_run_name="handle message in {channel}/{thread_ts}",
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
        # Get response from agent
        response = await run_agent(
            message=message,
            thread_ts=thread_ts,
            channel=channel,
        )

        logger.info(f"Got response for thread {thread_ts}")
        logger.debug(f"Response: {response}")
        # Send response to Slack
        logger.debug(f"Sending message to {channel} with thread_ts {thread_ts}")

        await send_slack_message(
            text=response,
            thread_ts=thread_ts,
            channel=channel,
        )
        logger.info(f"Completed processing for thread {thread_ts}")
    except Exception as e:
        logger.error(f"Error processing message in thread {thread_ts}: {e}")
        # Send error message to Slack
        await send_slack_message(
            text="Sorry, I encountered an error while processing your message.",
            thread_ts=thread_ts,
            channel=channel,
        )
