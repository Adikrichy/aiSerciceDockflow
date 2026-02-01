import asyncio
import os
from dotenv import load_dotenv

# Import exactly as in gemini_client.py
try:
    from google import genai
    print("SUCCESS: 'from google import genai' worked")
except ImportError as e:
    print(f"FAILURE: 'from google import genai' failed: {e}")
    exit(1)

async def test_gemini():
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    
    if not api_key:
        print("ERROR: GEMINI_API_KEY not found in .env")
        return

    print(f"Testing Gemini with model: {model_name}")
    print(f"API Key present: {bool(api_key)}")

    try:
        client = genai.Client(api_key=api_key)
        
        # Sync call (blocking) - wrapped in executor similarly to gemini_client.py logic
        # But for this simple test we can call it directly if the SDK supports sync.
        # The new SDK client methods are sync by default?
        # gemini_client.py puts it in executor, which implies it IS blocking.
        
        response = client.models.generate_content(
            model=model_name,
            contents="Hello, simply answer OK.",
            config=genai.types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        
        print(f"GEMINI RESPONSE: {response.text}")

    except Exception as e:
        print(f"GEMINI ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_gemini())
