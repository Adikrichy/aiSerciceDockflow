import requests
import json
from .base import LlmClient
from ..config import settings
import asyncio


class OllamaClient(LlmClient):
    def __init__(self):
        self.base_url = settings.ollama_base_url.rstrip('/')
        self.model = settings.ollama_model

    async def generate(self, prompt: str) -> str:
        try:
            # Prepare the request payload
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False
            }
            
            # Run the synchronous HTTP request in a thread pool
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=120  # 2 minutes timeout for local processing
                )
            )
            
            if response.status_code == 200:
                result = response.json()
                if "response" in result:
                    return result["response"].strip()
                else:
                    return "[Ollama returned invalid response format]"
            else:
                return f"[Ollama API Error: {response.status_code} - {response.text}]"
                
        except Exception as e:
            print(f"Ollama API error: {str(e)}")
            return f"[Ollama API Error: {str(e)}]"