import asyncio
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

try:
    with open('classification/prompts.py', 'r', encoding='utf-8') as f:
        SYSTEM_PROMPT = f.read().split('SYSTEM_PROMPT = ')[1].strip('\"\"\"\n')
except OSError:
    SYSTEM_PROMPT = "Sei un assistente."

class SchemaStrings(BaseModel):
    reasoning: str
    title: str
    summary: str
    published_at: str
    source_url: str
    country_code: str
    latitude: float
    longitude: float
    companies_involved: str = Field(description="Aziende separate da virgola. 'Nessuna' se vuoto.")
    tags: str = Field(description="Tag separati da virgola.")
    primary_category: str
    sentiment: str
    infrastructural_entities: str = Field(description="Infrastrutture separate da virgola. 'Nessuna' se vuoto.")
    relevance_level: int

async def test_schema(schema_cls, title, content):
    client = genai.Client()
    user_message = f"TITOLO: {title}\nCONTENUTO: {content}"
    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model='gemma-4-31b-it',
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type='application/json',
                response_schema=schema_cls,
                temperature=0.3
            )
        )
        print('SUCCESS:', response.text[:100].replace('\n', ' '))
        return True
    except Exception as e:
        print('FAILED:', str(e)[:100])
        return False

async def main():
    title = 'JPEG-XL Libjxl 0.12 Brings More Performance Optimizations'
    content = 'The Libjxl 0.12 release is here for this widely-used JPEG-XL implementation. Libjxl 0.12 comes with some speed-ups...'
    print('Testing SchemaStrings on JPEG-XL...')
    await test_schema(SchemaStrings, title, content)

if __name__ == '__main__':
    asyncio.run(main())
