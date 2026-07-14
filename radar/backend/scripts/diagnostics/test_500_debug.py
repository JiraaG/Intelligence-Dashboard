import asyncio
import os
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import List, Literal

try:
    with open('classification/prompts.py', 'r', encoding='utf-8') as f:
        SYSTEM_PROMPT = f.read().split('SYSTEM_PROMPT = ')[1].strip('\"\"\"\n')
except:
    SYSTEM_PROMPT = "Sei un assistente."

class FullSchema(BaseModel):
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
    primary_category: Literal[
        'Nucleare', 'Energia', 'Infrastrutture',
        'Geopolitica', 'Economia', 'Tecnologia',
        'Spazio', 'Ambiente', 'Salute', 'Sicurezza'
    ]
    sentiment: Literal['Positivo', 'Neutrale', 'Negativo']
    infrastructural_entities: List[str]
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
        print('SUCCESS:', response.text[:100])
        return True
    except Exception as e:
        print('FAILED:', e)
        return False

class SchemaNoLiterals(BaseModel):
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
    infrastructural_entities: List[str]
    relevance_level: int

class SchemaNoLists(BaseModel):
    reasoning: str
    title: str
    summary: str
    published_at: str
    source_url: str
    country_code: str
    latitude: float
    longitude: float
    relevance_level: int
    primary_category: str
    sentiment: str

class SchemaNoFloats(BaseModel):
    reasoning: str
    title: str
    summary: str
    published_at: str
    source_url: str
    country_code: str
    companies_involved: List[str]
    tags: List[str]
    primary_category: Literal['Nucleare', 'Energia', 'Infrastrutture', 'Geopolitica', 'Economia', 'Tecnologia', 'Spazio', 'Ambiente', 'Salute', 'Sicurezza']
    sentiment: Literal['Positivo', 'Neutrale', 'Negativo']
    infrastructural_entities: List[str]
    relevance_level: int

async def main():
    title = 'JPEG-XL Libjxl 0.12 Brings More Performance Optimi'
    content = 'JPEG-XL Libjxl 0.12 has been released with many optimizations.'
    
    print('Testing SchemaNoLiterals...')
    await test_schema(SchemaNoLiterals, title, content)
    
    print('Testing SchemaNoLists...')
    await test_schema(SchemaNoLists, title, content)
    
    print('Testing SchemaNoFloats...')
    await test_schema(SchemaNoFloats, title, content)

if __name__ == '__main__':
    asyncio.run(main())
