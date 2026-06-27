"""ARQ worker process — runs audit tasks + periodic schedule check."""

import os
from arq import create_pool
from arq.worker import Worker as ArqWorker
from community_ai_audit.core.tasks import run_audit_task, check_schedules

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")


async def startup(ctx: dict) -> None:
    ctx["redis"] = await create_pool(REDIS_URL)


async def shutdown(ctx: dict) -> None:
    if redis := ctx.get("redis"):
        await redis.close()


class WorkerSettings:
    functions = [run_audit_task, check_schedules]
    redis_settings = {"host": "localhost", "port": 6379}
    on_startup = startup
    on_shutdown = shutdown
    cron_jobs = [("*/1", check_schedules.__name__)]


async def run_worker():
    worker = ArqWorker(WorkerSettings)
    await worker.run()


if __name__ == "__main__":
    import asyncio

    asyncio.run(run_worker())
