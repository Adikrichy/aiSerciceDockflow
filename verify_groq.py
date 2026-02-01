import asyncio
import os
from dotenv import load_dotenv

# Import exactly as in groq_client.py
try:
    from groq import Groq
    print("SUCCESS: 'from groq import Groq' worked")
except ImportError as e:
    print(f"FAILURE: 'from groq import Groq' failed: {e}")
    exit(1)

async def test_groq():
    load_dotenv()
    api_key = os.getenv("GROQ_API_KEY")
    model_name = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    
    if not api_key:
        print("ERROR: GROQ_API_KEY not found in .env")
        return

    print(f"Testing Groq with model: {model_name}")
    print(f"API Key present: {bool(api_key)}")

    try:
        client = Groq(api_key=api_key)
        
        loop = asyncio.get_event_loop()
        
        def sync_call():
             return client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": "Hello, simply answer OK.",
                    }
                ],
                model=model_name,
            )

        response = await loop.run_in_executor(None, sync_call)
        
        if response.choices and response.choices[0].message.content:
            print(f"GROQ RESPONSE: {response.choices[0].message.content}")
        else:
            print("GROQ EMPTY RESPONSE")

    except Exception as e:
        print(f"GROQ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_groq())
