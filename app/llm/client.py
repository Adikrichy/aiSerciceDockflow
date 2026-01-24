import json

from ..config import settings
from .base import LlmClient


class MockLlmClient(LlmClient):
    async def generate(self, prompt: str) -> str:
        if "JSON schema" in prompt or '"doc_type"' in prompt:
            mock = {
                "doc_type": "contract",
                "language": "ru",
                "semantic_summary": {
                    "purpose": "Оказание услуг по разработке ПО (mock)",
                    "audience": "Менеджмент и технические специалисты (mock)",
                    "expected_actions": ["Подписание договора", "Согласование ТЗ"]
                },
                "requirements": [
                    "Сдача работ по акту",
                    "Оплата в течение 10 дней"
                ],
                "recommendations": [
                    "Проверить наличие всех приложений к договору"
                ],
                "risks": [
                    {
                        "type": "MISSING_SIGNATURE",
                        "description": "Электронные подписи сторон не найдены в тексте (mock)",
                        "severity": "high"
                    }
                ],
                "ambiguities": [
                    "Не указана конкретная дата начала работ"
                ],
                "workflow_decision": {
                    "suggested_reviewers": ["Legal", "CEO"],
                    "approval_complexity": "multi-step",
                    "decision_flags": {
                        "can_auto_approve": False,
                        "requires_human_review": True,
                        "missing_mandatory_info": False
                    },
                    "analysis_confidence": 0.95
                }
            }
            return json.dumps(mock, ensure_ascii=False)

        return f"[MOCK LLM ANSWER] {prompt[:200]}"


def create_llm_client(provider: str | None = None) -> LlmClient:
    provider = provider or settings.llm_provider

    if provider == "mock":
        return MockLlmClient()

    # ленивые импорты, чтобы вообще исключить циклы
    if provider == "gemini":
        from .gemini_client import GeminiClient
        return GeminiClient()
    if provider == "groq":
        from .groq_client import GroqClient
        return GroqClient()
    if provider == "ollama":
        from .ollama_client import OllamaClient
        return OllamaClient()

    raise ValueError(f"Unknown LLM provider: {provider}. Valid options: mock, gemini, groq, ollama")