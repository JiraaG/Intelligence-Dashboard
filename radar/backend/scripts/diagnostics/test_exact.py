import asyncio
from google import genai
from google.genai import types
from classification.validator import GeopoliticalArticleSchema
from classification.prompts import SYSTEM_PROMPT

async def main():
    title = 'Is there any verified/signed bot traffic?'
    content = 'I am looking for verified bot traffic for my website.'
    client = genai.Client()
    user_message = f"TITOLO: {title}\nCONTENUTO: {content}"
    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model='gemini-3.1-flash-lite',
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type='application/json',
                response_schema=GeopoliticalArticleSchema,
                temperature=0.3
            )
        )
        print('SUCCESS:', response.text[:100])
    except Exception as e:
        print('FAILED:', e)

if __name__ == '__main__':
    asyncio.run(main())
