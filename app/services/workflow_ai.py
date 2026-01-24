from app.llm.client import LlmClient


class WorkflowAiService:
    def __init__(self, llm_factory):
        self._llm_factory = llm_factory

    async def suggest(self, payload: dict) -> dict:
        """
               payload пример:
               {
                 "document_type": "Contract",
                 "roles": ["Worker", "CEO"],
                 "goal": "Approve contract",
                 "provider": "gemini" 
               }
        """
        document_type = payload.get("document_type", "Unknown")
        roles = payload.get("roles", [])
        goal = payload.get("goal", "Unknown")
        provider = payload.get("provider")

        prompt = (
            "Suggest a simple approval workflow.\n"
            f"Document type: {document_type}\n"
            f"Roles: {roles}\n"
            f"Goal: {goal}\n"
            "Return JSON with steps [{order, role, action}]."
        )

        llm = self._llm_factory(provider) if provider else self._llm_factory()
        answer = await llm.generate(prompt)
        return {"suggestions_raw": answer}