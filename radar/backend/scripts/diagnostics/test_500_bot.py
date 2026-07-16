import asyncio
from google import genai
from google.genai import types
from pydantic import BaseModel
from typing import List

try:
    with open('classification/prompts.py', 'r', encoding='utf-8') as f:
        SYSTEM_PROMPT = f.read().split('SYSTEM_PROMPT = ')[1].strip('\"\"\"\n')
except OSError:
    SYSTEM_PROMPT = "Sei un assistente."

class SchemaFull(BaseModel):
    reasoning: str
    title: str
    summary: str
    published_at: str
    source_url: str
    country_code: str
    latitude: float
    longitude: float
    companies_involved: List[str]
    tags: List[str]
    primary_category: str
    sentiment: str
    infrastructural_entities: List[str]
    relevance_level: int

class SchemaNoTags(BaseModel):
    reasoning: str
    title: str
    summary: str
    published_at: str
    source_url: str
    country_code: str
    latitude: float
    longitude: float
    companies_involved: List[str]
    primary_category: str
    sentiment: str
    infrastructural_entities: List[str]
    relevance_level: int

class SchemaNoCompanies(BaseModel):
    reasoning: str
    title: str
    summary: str
    published_at: str
    source_url: str
    country_code: str
    latitude: float
    longitude: float
    tags: List[str]
    primary_category: str
    sentiment: str
    infrastructural_entities: List[str]
    relevance_level: int

class SchemaNoListsAtAll(BaseModel):
    reasoning: str
    title: str
    summary: str
    published_at: str
    source_url: str
    country_code: str
    latitude: float
    longitude: float
    primary_category: str
    sentiment: str
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
        print('SUCCESS:', response.text[:50].replace('\n', ' '))
        return True
    except Exception as e:
        print('FAILED:', str(e)[:100])
        return False

async def main():
    title = 'Is there any verified/signed bot traffic?'
    content = 'I am looking for verified bot traffic for my website.'
    
    print('Testing SchemaFull...')
    await test_schema(SchemaFull, title, content)
    
    print('Testing SchemaNoTags...')
    await test_schema(SchemaNoTags, title, content)
    
    print('Testing SchemaNoCompanies...')
    await test_schema(SchemaNoCompanies, title, content)
    
    print('Testing SchemaNoListsAtAll...')
    await test_schema(SchemaNoListsAtAll, title, content)

if __name__ == '__main__':
    asyncio.run(main())
