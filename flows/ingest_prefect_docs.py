# /// script
# dependencies = [
#     "prefect",
#     "raggy[chroma]",
# ]
# ///

from typing import Literal

from chromadb.api.models.Collection import Document as ChromaDocument
from prefect import flow, task
from raggy.documents import Document
from raggy.loaders.base import Loader
from raggy.loaders.github import GitHubRepoLoader
from raggy.loaders.web import SitemapLoader
from raggy.vectorstores.chroma import Chroma, ChromaClientType

prefect_loaders = [
    SitemapLoader(
        urls=[
            "https://docs-3.prefect.io/sitemap.xml",
            "https://prefect.io/sitemap.xml",
        ],
        exclude=["api-ref", "www.prefect.io/events"],
    ),
    GitHubRepoLoader(
        repo="PrefectHQ/prefect",
        include_globs=["**/*.md", "src/prefect/*.py", "flows/*.py"],
    ),
]


@task(task_run_name="Run {loader.__class__.__name__}")
async def run_loader(loader: Loader) -> list[Document]:
    return await loader.load()


@task
def add_documents(
    chroma: Chroma, documents: list[Document], mode: Literal["upsert", "reset"]
) -> list[ChromaDocument]:
    if mode == "reset":
        chroma.reset_collection()
        docs = chroma.add(documents)
    elif mode == "upsert":
        docs = chroma.upsert(documents)
    return docs


@flow(name="Update Knowledge", log_prints=True)
def refresh_chroma(
    collection_name: str = "prefect",
    chroma_client_type: ChromaClientType = "cloud",
    mode: Literal["upsert", "reset"] = "upsert",
):
    """Flow updating vectorstore with info from the Prefect community."""
    documents: list[Document] = [
        doc
        for future in run_loader.map(prefect_loaders)  # type: ignore
        for doc in future.result()  # type: ignore
    ]

    print(f"Loaded {len(documents)} documents from the Prefect community.")

    with Chroma(
        collection_name=collection_name, client_type=chroma_client_type
    ) as chroma:
        docs = add_documents(chroma, documents, mode)

        print(f"Added {len(docs)} documents to the {collection_name} collection.")  # type: ignore


if __name__ == "__main__":
    refresh_chroma(collection_name="test", chroma_client_type="base", mode="reset")
