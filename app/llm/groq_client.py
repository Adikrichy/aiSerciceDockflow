from groq import Groq
from .base import LlmClient
from ..config import settings
import asyncio


class GroqClient(LlmClient):
    def __init__(self):
        if not settings.groq_api_key:
            raise ValueError("GROQ_API_KEY is required for Groq provider")
        
        self.client = Groq(api_key=settings.groq_api_key)

    async def generate(self, prompt: str, is_json: bool = True) -> str:
        try:
            # Run the synchronous Groq API call in a thread pool
            loop = asyncio.get_event_loop()
            
            # Add timeout to prevent infinite hangs
            try:
                response = await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        lambda: self.client.chat.completions.create(
                            messages=[
                                {
                                    "role": "user",
                                    "content": prompt,
                                }
                            ],
                            model=settings.groq_model,
                        )
                    ),
                    timeout=60.0  # 60 seconds timeout
                )
            except asyncio.TimeoutError:
                raise Exception("Groq API call timed out after 60 seconds")
            
            if response.choices and response.choices[0].message.content:
                return response.choices[0].message.content.strip()
            else:
                raise Exception("Groq API returned empty response")
                
        except Exception as e:
            # Rethrow to let DocumentAiService handle retry/error
            raise Exception(f"Groq API error: {str(e)}") from e