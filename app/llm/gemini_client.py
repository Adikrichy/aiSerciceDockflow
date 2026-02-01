from google import genai
from .base import LlmClient
from ..config import settings
import asyncio


class GeminiClient(LlmClient):
    def __init__(self):
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is required for Gemini provider")

        # Новый SDK использует объект Client
        self.client = genai.Client(api_key=settings.gemini_api_key)
        # Сохраняем имя модели (например, 'gemini-2.0-flash')
        self.model_name = settings.gemini_model

    async def generate(self, prompt: str, is_json: bool = True) -> str:
        try:
            # Выполняем синхронный вызов в экзекуторе,
            # так как методы Client в текущей версии SDK блокирующие
            loop = asyncio.get_event_loop()

            def sync_generate():
                from google.genai import types
                config = None
                if is_json:
                    config = types.GenerateContentConfig(
                        response_mime_type="application/json"
                    )
                return self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=config
                )

            # Add timeout to prevent infinite hangs
            try:
                response = await asyncio.wait_for(
                    loop.run_in_executor(None, sync_generate),
                    timeout=60.0  # 60 seconds timeout
                )
            except asyncio.TimeoutError:
                raise Exception("Gemini API call timed out after 60 seconds")

            if response and response.text:
                return response.text.strip()
            else:
                raise Exception("Gemini API returned empty response")

        except Exception as e:
            # Rethrow to let DocumentAiService handle retry/error
            raise Exception(f"Gemini API error: {str(e)}") from e