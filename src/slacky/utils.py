import hashlib
import hmac
import re
import time
from typing import TypedDict, Unpack

import httpx
from fastapi import Request
from prefect import task

from .logging import get_logger
from .settings import settings

logger = get_logger(__name__)


class SlackMessage(TypedDict):
    """A Slack message to send to the API."""

    channel: str
    thread_ts: str
    text: str


def scrub_app_mention(message: str) -> str:
    """Remove app mention from the message."""
    # Remove any <@U...> mentions from the start of the message
    cleaned = re.sub(r"^\s*<@[A-Z0-9]+>\s*", "", message)
    return cleaned.strip()


def is_positive_reaction(reaction: str | None) -> bool:
    """Check if the reaction is a thumbs up or down."""
    return reaction in ("+1", "thumbsup")


def get_channel_name(channel_id: str) -> str:
    """Get the name of a channel from its ID."""
    with httpx.Client() as client:
        response = client.get(
            f"https://slack.com/api/conversations.info?channel={channel_id}",
            headers={
                "Authorization": f"Bearer {settings.bot_token.get_secret_value()}"
            },
        )
        response.raise_for_status()
        return response.json().get("channel", {}).get("name")


def convert_md_links_to_slack(text: str) -> str:
    """Convert Markdown links to Slack-style links."""
    md_link_pattern = r"\[(?P<text>[^\]]+)]\((?P<url>[^\)]+)\)"

    def to_slack_link(match: re.Match[str]) -> str:
        return f'<{match.group("url")}|{match.group("text")}>'

    slack_text = re.sub(md_link_pattern, to_slack_link, text)

    slack_text = re.sub(r"\*\*(.*?)\*\*", r"*\1*", slack_text)

    return slack_text


@task
async def send_slack_message(**slack_message_kwargs: Unpack[SlackMessage]) -> None:
    """Send a message to Slack."""
    logger = get_logger(__name__)
    message = slack_message_kwargs.get("text")
    logger.info(f"Sending message to Slack: {message}")

    if not message:
        logger.warning("No message to send to Slack")
        return

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://slack.com/api/chat.postMessage",
            headers={
                "Authorization": f"Bearer {settings.bot_token.get_secret_value()}"
            },
            json=slack_message_kwargs | {"text": convert_md_links_to_slack(message)},
        )
        response.raise_for_status()


async def verify_slack_request(request: Request) -> bool:
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
