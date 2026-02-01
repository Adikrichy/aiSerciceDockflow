import os
import logging
import time
from app.llm.client import create_llm_client
from app.schemas.messages import ChatPayload, ChatResult

class ChatAiService:
    def __init__(self, document_service=None):
        self._document_service = document_service
        self._company_context = self._load_company_context()

    def _load_company_context(self) -> str:
        context_path = os.path.join(os.getcwd(), "data", "company_context.md")
        if os.path.exists(context_path):
            try:
                with open(context_path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception as e:
                logging.getLogger(__name__).error(f"Failed to load company context: {e}")
        return ""

    async def chat(self, payload: dict) -> dict:
        start_time = time.time()
        chat_payload = ChatPayload(**payload)
        
        # Determine provider
        user_provider = payload.get("context", {}).get("provider")
        llm_client = create_llm_client(user_provider)
        
        # Build document context
        document_text = None
        if chat_payload.document_id and self._document_service:
            try:
                from app.schemas.messages import DocumentAnalyzePayload
                doc_p = DocumentAnalyzePayload(
                    document_id=chat_payload.document_id,
                    version_id=chat_payload.version_id,
                    file_url=chat_payload.file_url,
                    service_token=chat_payload.service_token,
                    mime_type=chat_payload.mime_type,
                    file_name=chat_payload.file_name,
                    file_size=chat_payload.file_size
                )
                extract_start = time.time()
                document_text = await self._document_service._get_document_text(doc_p)
                logging.getLogger(__name__).info(f"Document extraction took {time.time() - extract_start:.2f}s for document {chat_payload.document_id}")
            except Exception as e:
                logging.getLogger(__name__).error(f"Failed to fetch document text for chat: {e}")

        # Build conversation history text
        history_text = ""
        if chat_payload.history:
            history_text = "\nPREVIOUS DIALOGUE:\n"
            for msg in chat_payload.history:
                sender_label = msg.get("sender", "User")
                role = msg.get("role", "user")
                if role == "assistant":
                    sender_label = "AI Assistant"
                history_text += f"{sender_label}: {msg.get('content')}\n"
            history_text += "---\n"

        # Specialized Prompts
        if chat_payload.chat_type == "DOCUMENT":
            system_prompt = (
                "You are **DockFlow Document AI**, a specialized assistant focused ONLY on the currently open document and workflow.\n\n"
                "RESTRICTIONS:\n"
                "1. **Strict Context**: You must only answer questions related to the document content provided below or the workflow associated with it.\n"
                "2. **No General Chat**: If the user asks general questions, off-topic questions (e.g., 'Who is stronger, me or a robot?'), or anything unrelated to this document, you MUST politely refuse. "
                "Response example: 'Я здесь только для того, чтобы обсудить этот документ или воркфлоу. Для общих вопросов, пожалуйста, перейдите в основной чат с AI Assistant.'\n"
                "3. **Tone**: Professional, precise, and helpful within your domain.\n\n"
                "CURRENT DOCUMENT CONTEXT:\n"
                f"{document_text if document_text else 'No document content available.'}\n\n"
                f"{history_text}"
                f"The user ({chat_payload.sender_name}) just said (LATEST MESSAGE): \"{chat_payload.content}\"\n"
            )
        else: # GENERAL
            system_prompt = (
                "You are **DockFlow AI**, a friendly and professional AI assistant integrated into the DockFlow system. "
                "You are an expert on the DockFlow project and the company using it.\n\n"
                "GUIDELINES:\n"
                "1. **Company Knowledge**: Use the company information provided below to answer questions about the project, company structure, and procedures.\n"
                "2. **Stay on Topic**: Your scope is limited to DockFlow, document management, and professional work within the company. "
                "If the user asks off-topic questions (e.g., 'Who is stronger, me or a robot?', 'Tell me about space'), politely redirect them to discuss the project. "
                "Response example: 'Я специализируюсь на проекте DockFlow и корпоративных процессах. Давайте обсудим ваши документы или как я могу помочь вам в работе.'\n"
                "3. **Tone**: Helpful, polite, and professional.\n"
                "4. **Language**: Always respond in the same language as the user (default to Russian).\n\n"
                "COMPANY CONTEXT:\n"
                f"{self._company_context}\n\n"
                f"{history_text}"
                f"The user ({chat_payload.sender_name}) just said (LATEST MESSAGE): \"{chat_payload.content}\"\n"
            )

        # Call LLM
        llm_start = time.time()
        response_text = await llm_client.generate(system_prompt, is_json=False)
        logging.getLogger(__name__).info(f"LLM generation took {time.time() - llm_start:.2f}s")

        result = ChatResult(
            response=response_text,
            channel_id=chat_payload.channel_id,
            used_model=llm_client.__class__.__name__
        )
        
        logging.getLogger(__name__).info(f"Total chat processing took {time.time() - start_time:.2f}s")
        return result.model_dump()
