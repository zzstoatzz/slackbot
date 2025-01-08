from typing import TypedDict

import httpx
from prefect import flow, task
from prefect.events import get_events_subscriber
from prefect.settings import PREFECT_UI_URL
from raggy.documents import Document
from raggy.vectorstores.chroma import Chroma

from .agent import get_agent
from .logging import get_logger
from .settings import settings
from .tools import query_knowledgebase
from .utils import get_channel_name, send_slack_message

logger = get_logger(__name__)


class QAPair(TypedDict):
    question: str
    answer: str


@task
async def summarize_conversation(
    conversation: str, thread_ts: str, channel: str
) -> QAPair:
    """Summarize a conversation into a Q&A pair."""
    agent = get_agent(result_type=QAPair, tools=[query_knowledgebase])
    return await agent.handle_message(conversation, thread_ts, channel)


@flow
async def process_liked_response(thread_ts: str, channel: str) -> None:
    """Process a liked response by saving it to the knowledgebase."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://slack.com/api/conversations.replies",
            params={"channel": channel, "ts": thread_ts},
            headers={
                "Authorization": f"Bearer {settings.bot_token.get_secret_value()}"
            },
        )
        response.raise_for_status()
        thread = response.json()

    if not thread.get("messages"):
        logger.warning(f"No messages found in thread {thread_ts}")
        return

    # Combine all messages in the thread
    conversation = "\n".join(
        f"{msg.get('user', msg.get('bot_id', 'unknown'))}: {msg['text']}"
        for msg in thread["messages"]
    )

    qa_pair = await summarize_conversation(conversation, thread_ts, channel)
    summary = f"Q: {qa_pair['question']}\nA: {qa_pair['answer']}"
    document = Document(
        text=summary,
        metadata={
            "thread_ts": thread_ts,
            "channel": channel,
            "channel_name": get_channel_name(channel),
            "type": "liked_thread",
            "source": "slack",
            "raw_conversation": conversation,
        },
    )
    logger.info(f"Saved summary to knowledgebase: {summary}")

    with Chroma(
        collection_name=settings.namespace,
        client_type=settings.chroma_client_type,
    ) as vectorstore:
        vectorstore.add([document])
        logger.info(f"Saved liked thread {thread_ts} to knowledgebase")


async def listen_for_events() -> None:
    """Listen for events and handle them."""

    async with get_events_subscriber(filter=None) as subscriber:
        async for event in subscriber:
            logger.info(f"📥 event: {event.event}")

            if event.event == "slackbot.response.liked":
                thread_ts = event.resource.get("prefect.resource.id")
                channel = event.resource.get("channel")

                if thread_ts and channel:
                    await process_liked_response(thread_ts=thread_ts, channel=channel)
                else:
                    logger.warning(
                        "Missing thread_ts or channel in liked response event"
                    )

            if event.event == "prefect.flow-run.Completed" and any(
                resource.get("prefect.resource.id") == "prefect.tag.ai-triggered"
                and resource.get("prefect.resource.role") == "tag"
                for resource in event.related
            ):
                flow_run_resource_id = event.resource.get("prefect.resource.id")
                assert flow_run_resource_id
                flow_run_id = flow_run_resource_id.split(".")[-1]
                flow_run_url = f"{PREFECT_UI_URL}/runs/flow-run/{flow_run_id}"
                await send_slack_message(
                    channel=settings.notification_channel_id,
                    text=(
                        f"hey your flow run I triggered earlier is complete\n"
                        f"view it [here]({flow_run_url})"
                    ),
                )
