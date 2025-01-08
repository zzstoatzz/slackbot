from prefect import Flow, flow


@flow
def some_heavy_work_elsewhere():
    pass


if __name__ == "__main__":
    flow_from_source = some_heavy_work_elsewhere.from_source(
        source="https://github.com/zzstoatzz/slackbot.git",
        entrypoint="flows/remote_heavy_work.py",
    )
    assert isinstance(flow_from_source, Flow)
    flow_from_source.deploy(
        name="remote-heavy-work",
        work_pool_name="remote-runtime",
        tags=["ai-can-trigger"],
    )
