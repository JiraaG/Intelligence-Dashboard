
import asyncio
import logging
import sys
sys.path.append('/app')
from app.classification.client import ClassificationClient

logging.basicConfig(level=logging.DEBUG)

async def main():
    client = ClassificationClient()
    
    print('Test 1: Global EV Sales...')
    try:
        res1 = await client.classify_article(
            'Gas Vs. Electric: Global EV Sales Are Actually Rising In 2026; Heres Where',
            'Global EV sales are rising everywhere in the world despite what some say.',
            'https://example.com/ev',
            '2026-07-11'
        )
        print('Successo Test 1')
    except Exception as e:
        print('Errore Test 1:', e)

if __name__ == '__main__':
    asyncio.run(main())

