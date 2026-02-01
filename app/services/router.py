from app.schemas.messages import AiTask
from app.services.chat_ai import ChatAiService


class TaskRouter:
    def __init__(self, document_service, workflow_service):
        self._document_service = document_service
        self._workflow_service = workflow_service
        self._chat_service = ChatAiService(document_service)

    async def handle(self, task: AiTask) -> dict:
        if task.type == "PING":
            return {"pong": True}

        if task.type == "DOCUMENT_ANALYZE":
            return await self._document_service.analyze(task.payload)

        if task.type == "DOCUMENT_REVIEW":
            return await self._document_service.review(task.payload)

        if task.type == "WORKFLOW_SUGGEST":
            return await self._workflow_service.suggest(task.payload)

        if task.type == "CHAT":
            return await self._chat_service.chat(task.payload)

        raise ValueError(f"Unknown task type: {task.type}")
