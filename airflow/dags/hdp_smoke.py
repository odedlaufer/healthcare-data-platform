"""Smoke DAG: proves the scheduler, DAG processor and LocalExecutor run a task end to end."""

from airflow.sdk import dag, task


@dag(schedule=None, catchup=False, tags=["smoke"])
def hdp_smoke() -> None:
    @task
    def hello() -> str:
        return "ok"

    hello()


hdp_smoke()
