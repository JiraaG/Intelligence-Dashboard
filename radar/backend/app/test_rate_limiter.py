import asyncio
import time
import logging
from app.classification.client import ClassificationClient
from app.core.config import LLM_RPM

# Configura logger per vedere i messaggi
logging.basicConfig(level=logging.DEBUG)

async def test_worker(client, worker_id):
    print(f"Worker {worker_id} sta chiedendo il lock...")
    await client._wait_for_rate_limit()
    print(f"[{time.strftime('%X')}] Worker {worker_id} ha superato il rate limit (dovrebbe esserci uno spazio di {60.0/LLM_RPM}s rispetto al precedente).")

async def main():
    print(f"Test avviato. LLM_RPM configurato: {LLM_RPM}")
    client = ClassificationClient()
    
    # Lanciamo 5 richieste simultanee
    async with asyncio.TaskGroup() as tg:
        for i in range(5):
            tg.create_task(test_worker(client, i))

if __name__ == "__main__":
    asyncio.run(main())
