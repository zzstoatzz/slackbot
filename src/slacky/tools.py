import asyncio
from typing import Any

import httpx
from prefect import flow, task
from prefect.client.schemas.objects import FlowRun
from prefect.deployments import run_deployment
from raggy.loaders.github import GitHubRepoLoader
from raggy.loaders.web import SitemapLoader
from raggy.vectorstores.chroma import Chroma, query_collection

from .settings import settings
from .utils import get_logger

logger = get_logger(__name__)


def add_sitemap_to_knowledgebase(
    sitemap_url: str, collection_name: str = "slacky"
) -> str:
    """Add a sitemap (like https://prefect.io/sitemap.xml) to the knowledgebase.

    Args:
        sitemap_url: The sitemap URL to add to the knowledgebase.

    Returns:
        A message indicating the number of documents added to the knowledgebase.
    """
    loader = SitemapLoader(urls=[sitemap_url])
    documents = asyncio.run(loader.load())
    namespace = collection_name or settings.namespace
    with Chroma(
        collection_name=namespace,
        client_type=settings.chroma_client_type,
    ) as vectorstore:
        documents = vectorstore.add(documents)
        message = (
            f"Added {len(documents)} documents from {sitemap_url} to the knowledgebase"
        )
        logger.info(message)
        return message


def add_github_repo_to_knowledgebase(repo: str, collection_name: str = "slacky") -> str:
    """Add a GitHub repo to the knowledgebase.

    Args:
        repo: The GitHub repo to add to the knowledgebase (e.g. "prefecthq/prefect")

    Returns:
        A message indicating the number of documents added to the knowledgebase.
    """
    loader = GitHubRepoLoader(repo=repo, include_globs=["README.md", "**/*.py"])
    documents = asyncio.run(loader.load())
    namespace = collection_name or settings.namespace
    with Chroma(
        collection_name=namespace,
        client_type=settings.chroma_client_type,
    ) as vectorstore:
        documents = vectorstore.add(documents)
        message = f"Added {len(documents)} documents from {repo} to the knowledgebase"
        logger.info(message)
        return message


@flow
def query_knowledgebase(queries: list[str], collection_name: str = "slacky") -> str:
    """Query the knowledgebase and return the answer. provide multiple queries
    to cover idiosyncrasies in the users phrasing and the knowledgebase.

    Args:
        queries: The queries to run.

    Returns:
        The answer to the queries.
    """
    namespace = collection_name or settings.namespace
    return "".join(
        task(query_collection)
        .map(queries, collection_name=namespace, max_tokens=600)
        .result()
    )


def google_search(query: str, num: int = 3) -> str:
    """Use google to search the internet.

    Args:
        query: The query to search for.
        num: The number of results to return.

    Returns:
        The results of the search.
    """
    response = httpx.get(
        "https://www.googleapis.com/customsearch/v1",
        params={
            "q": query,
            "key": settings.google_api_key.get_secret_value(),
            "cx": settings.google_cx.get_secret_value(),
            "num": num,
        },
    )
    response.raise_for_status()
    return response.json()


def trigger_prefect_deployment(
    deployment_name: str, parameters: dict[str, Any] | None = None
) -> str:
    """Trigger a run of a prefect deployment

    Args:
        deployment_name: The name of the deployment to run.
        parameters: The parameters to pass to the deployment.

    Returns:
        The result of the deployment run.
    """
    import prefect.main  # noqa # type: ignore

    flow_run = run_deployment(
        deployment_name,
        parameters=parameters,
        timeout=0,
        tags=["ai-triggered"],
    )
    assert isinstance(flow_run, FlowRun) and flow_run.state is not None
    assert flow_run.state.is_scheduled()
    return f"Triggered deployment {deployment_name} with parameters {parameters}"
