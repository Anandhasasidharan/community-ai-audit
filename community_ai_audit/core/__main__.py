"""Entry point: python3 -m community_ai_audit.core"""

from community_ai_audit.core.worker import run_worker

if __name__ == "__main__":
    import asyncio

    asyncio.run(run_worker())
