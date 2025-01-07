from prefect import task
from raggy.loaders.web import SitemapLoader
from raggy.vectorstores.chroma import Chroma, query_collection


@task
async def add_sitemap_to_knowledgebase(
    sitemap_url: str, namespace: str = "slacky"
) -> None:
    """Add a sitemap to the knowledgebase."""
    loader = SitemapLoader(urls=[sitemap_url])
    documents = await loader.load()
    with Chroma(collection_name=namespace) as vectorstore:
        vectorstore.add(documents)


@task
def query_knowledgebase(query: str, namespace: str = "slacky") -> str:
    """Query the knowledgebase and return the answer."""
    return query_collection(query_text=query, collection_name=namespace)
