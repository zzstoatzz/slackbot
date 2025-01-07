import logging
from typing import Any
from functools import lru_cache
from rich.console import Console
from rich.logging import RichHandler

console = Console()

@lru_cache
def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def setup_logging(
    level: str = "INFO",
    **logger_kwargs: Any,
) -> None:
    """Set up rich logging with the specified level.

    Args:
        level: The logging level to use
        **logger_kwargs: Additional kwargs to pass to logging.basicConfig
    """
    root_logger = logging.getLogger()
    if root_logger.handlers:
        for handler in root_logger.handlers:
            root_logger.removeHandler(handler)

    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[
            RichHandler(
                console=console,
                show_path=False,
                omit_repeated_times=False,
                rich_tracebacks=True,
            )
        ],
        **logger_kwargs,
    )
