from typing import Any, Callable, Generic, TypeAlias, TypedDict, TypeVar

from prefect.artifacts import create_markdown_artifact
from prefect.cache_policies import NONE
from pydantic import TypeAdapter
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models import KnownModelName, ModelSettings
from pydantic_core import to_json

from slacky.logging import get_logger
from slacky.settings import settings
from slacky.tools import (
    add_github_repo_to_knowledgebase,
    add_sitemap_to_knowledgebase,
    google_search,
    query_knowledgebase,
    trigger_prefect_deployment,
)
from slacky.wrap import WatchToolCalls

T = TypeVar("T")

logger = get_logger(__name__)
MessageHistoryCache: TypeAlias = dict[str, list[ModelMessage]]
MessageHistoryCacheAdapter = TypeAdapter(MessageHistoryCache)


def _load_message_cache() -> MessageHistoryCache:
    """Load the message cache from the settings file."""
    if not (cache_data := settings.message_cache_path.read_bytes()):
        return {}

    message_history = MessageHistoryCacheAdapter.validate_json(cache_data)
    logger.info("Loaded message history")
    for thread_ts, messages in message_history.items():
        logger.info(f"Thread {thread_ts} has {len(messages)} messages")
    return message_history


class ThreadContext(TypedDict):
    """Context for a Slack thread conversation."""

    thread_ts: str
    channel_id: str
    messages: list[ModelMessage]


class SlackAgent(Generic[T]):
    """A Slack agent powered by PydanticAI."""

    def __init__(
        self,
        model: KnownModelName,
        system_prompt: str | None = None,
        result_type: type[T] = str,
        tools: list[Callable[..., Any]] = [],
    ) -> None:
        """Initialize the agent with a model and optional system prompt."""
        self.model = model
        self._message_history: MessageHistoryCache = _load_message_cache()
        self._system_prompt = system_prompt or "You are a helpful Slack assistant."

        self.agent = Agent[ThreadContext, T](
            name="Slack agent",
            model=model,
            model_settings=ModelSettings(temperature=settings.ai_temperature),
            deps_type=ThreadContext,
            system_prompt=self._system_prompt,
            result_type=result_type,
            tools=tools,
        )

    def _save_message_cache(self) -> None:
        """Save the message cache to disk."""
        logger.info("Saving message history to disk")
        settings.message_cache_path.write_bytes(
            MessageHistoryCacheAdapter.dump_json(self._message_history, indent=2)
        )

    async def handle_message(
        self,
        message: str,
        thread_ts: str,
        channel_id: str,
        decorator_settings: dict[str, Any] | None = None,
    ) -> T:
        """Handle a message in a thread."""
        logger.info(f"Handling message in thread {thread_ts}")
        logger.info(
            f"Current message history keys: {list(self._message_history.keys())}"
        )

        # Get or create message history for this thread
        thread_messages = self._message_history.get(thread_ts, [])
        logger.info(
            f"Found {len(thread_messages)} existing messages for thread {thread_ts}"
        )
        logger.debug(f"Thread messages before: {thread_messages}")

        # Create thread context
        thread_context = ThreadContext(
            thread_ts=thread_ts,
            channel_id=channel_id,
            messages=thread_messages,
        )
        if decorator_settings is None:
            decorator_settings = {
                "cache_policy": NONE,
                "task_run_name": "execute {self.function.__name__}",
                "log_prints": True,
            }

        # Run the agent
        with WatchToolCalls(settings=decorator_settings):
            result = await self.agent.run(
                user_prompt=message,
                message_history=thread_messages,
                deps=thread_context,
            )

        await create_markdown_artifact(
            key="agent-response",
            markdown=f"""## {self.agent.name} responded in {channel_id}/{thread_ts}
### system prompt

{self._system_prompt}

### user prompt

{message}

### thread context

```json
{to_json(thread_context, indent=2).decode("utf-8")}
```

### response
{result.data}""",
            description="Agent response",
            _sync=False,  # type: ignore
        )

        # Update message history by extending existing messages
        new_messages = result.new_messages()
        if thread_ts not in self._message_history:
            self._message_history[thread_ts] = []
        self._message_history[thread_ts].extend(new_messages)

        # Save updated message history
        self._save_message_cache()

        logger.info(f"Updated thread {thread_ts} with {len(new_messages)} new messages")
        logger.debug(
            f"Thread now has {len(self._message_history[thread_ts])} total messages"
        )

        return result.data


def get_agent(
    tools: list[Callable[..., Any]] | None = None,
    system_prompt: str | None = None,
    result_type: type[T] = str,
) -> SlackAgent[T]:
    """Get the Slack agent."""
    if tools is None:
        tools = [
            query_knowledgebase,
            add_sitemap_to_knowledgebase,
            add_github_repo_to_knowledgebase,
            google_search,
            trigger_prefect_deployment,
        ]
    return SlackAgent[result_type](
        model=settings.ai_model,
        system_prompt=system_prompt or settings.base_system_prompt,
        tools=tools,
        result_type=result_type,
    )
