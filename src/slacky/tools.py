import asyncio

import httpx
from prefect import flow, task
from raggy.loaders.github import GitHubRepoLoader
from raggy.loaders.web import SitemapLoader
from raggy.vectorstores.chroma import Chroma, query_collection

from .settings import settings
from .utils import get_logger

logger = get_logger(__name__)


def add_sitemap_to_knowledgebase(sitemap_url: str, namespace: str = "slacky") -> None:
    """Add a sitemap (like https://prefect.io/sitemap.xml) to the knowledgebase."""
    loader = SitemapLoader(urls=[sitemap_url])
    documents = asyncio.run(loader.load())
    with Chroma(collection_name=namespace) as vectorstore:
        documents = vectorstore.add(documents)
        logger.info(
            f"Added {len(documents)} documents from {sitemap_url} to the knowledgebase"
        )


def add_github_repo_to_knowledgebase(repo: str, namespace: str = "slacky") -> None:
    """Add a GitHub repo to the knowledgebase.

    Args:
        repo: The GitHub repo to add to the knowledgebase (e.g. "prefecthq/prefect")
        namespace: The namespace to add the repo to.
    """
    loader = GitHubRepoLoader(repo=repo)
    documents = asyncio.run(loader.load())
    with Chroma(collection_name=namespace) as vectorstore:
        documents = vectorstore.add(documents)
        logger.info(
            f"Added {len(documents)} documents from {repo} to the knowledgebase"
        )


@task
def _run_single_query(query: str, namespace: str = "slacky") -> str:
    return query_collection(query_text=query, collection_name=namespace)


@flow
def query_knowledgebase(queries: list[str], namespace: str = "slacky") -> str:
    """Query the knowledgebase and return the answer. provide multiple queries
    to cover idiosyncrasies in the users phrasing and the knowledgebase.

    Args:
        queries: The queries to run.
        namespace: The namespace to query.

    Returns:
        The answer to the queries.
    """
    return "".join(_run_single_query.map(queries, namespace=namespace).result())


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
