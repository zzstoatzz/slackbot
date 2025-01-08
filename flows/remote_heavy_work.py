from prefect import flow


@flow
def some_heavy_work_elsewhere(x: int, y: int) -> int:
    return x * y


if __name__ == "__main__":
    # replace with a work pool if you need dynamic infra
    some_heavy_work_elsewhere.serve(name="remote-heavy-work")
