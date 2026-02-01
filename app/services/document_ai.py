from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from typing import Optional

import httpx
from docx import Document
from pypdf import PdfReader

from app.exceptions.document_errors import (
    DocumentAnalysisError,
    FileDownloadError,
    FileValidationError,
    JsonParsingError,
    LlmProcessingError,
    TextExtractionError
)
from app.llm.client import LlmClient
from app.schemas.messages import (
    DocumentAnalyzePayload, 
    DocumentAnalyzeResult,
    DocumentReviewPayload,
    DocumentReviewResult
)


MAX_TEXT_CHARS = 80_000  # ограничение, чтобы не улететь по токенам
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50MB limit
DOWNLOAD_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
DOWNLOAD_MAX_RETRIES = 3

logger = logging.getLogger(__name__)


class DocumentAiService:
    def __init__(self, llm_factory):
        self._llm_factory = llm_factory

    async def analyze(self, payload: dict) -> dict:
        try:
            # Add overall timeout for the whole analysis process
            return await asyncio.wait_for(self._do_analyze(payload), timeout=120.0)
        except asyncio.TimeoutError:
            logger.error("Document analysis timed out after 120 seconds", extra={"payload": payload})
            raise DocumentAnalysisError("Analysis timed out. Please try again or use a smaller document.")
        except Exception:
            raise

    async def _do_analyze(self, payload: dict) -> dict:
        try:
            p = DocumentAnalyzePayload.model_validate(payload)
            logger.info(
                "Starting document analysis",
                extra={
                    "document_id": p.document_id,
                    "version_id": p.version_id,
                    "file_url": str(p.file_url) if p.file_url else None,
                    "has_text": bool(p.text)
                }
            )
            
            # 1) Validate inputs
            if p.file_url:
                await self._validate_file_url(str(p.file_url))
            
            # 2) Extract text
            logger.info("Extracting text from document", extra={"document_id": p.document_id})
            text = await self._get_document_text(p)
            
            if not text.strip():
                logger.warning(
                    "No text extracted from document",
                    extra={
                        "document_id": p.document_id,
                        "version_id": p.version_id
                    }
                )
                empty = DocumentAnalyzeResult(
                    doc_type="other",
                    language="unknown",
                    summary=[],
                    key_fields={},
                    risks=[],
                    notes=["No text extracted (empty document or scanned PDF without OCR)."]
                )
                return empty.model_dump()

            # 3) Truncate if needed
            if len(text) > MAX_TEXT_CHARS:
                logger.info(
                    "Text truncated due to size limit",
                    extra={
                        "document_id": p.document_id,
                        "original_length": len(text)
                    }
                )
                text = text[:MAX_TEXT_CHARS] + "\n\n[TRUNCATED]"

            # 4) LLM analysis
            prompt = self._build_prompt(text)
            
            # Select LLM provider (payload specific or default)
            llm = self._llm_factory(p.provider) if p.provider else self._llm_factory()
            
            logger.info("Sending prompt to LLM", extra={"document_id": p.document_id, "provider": p.provider or "default"})
            answer = await self._generate_with_retry(prompt, llm=llm)

            # 5) Parse and validate result
            logger.info("Parsing LLM response", extra={"document_id": p.document_id})
            data = self._safe_json_loads(answer)
            result = DocumentAnalyzeResult.model_validate(data)
            
            logger.info(
                "Document analysis completed successfully",
                extra={
                    "document_id": p.document_id,
                    "version_id": p.version_id,
                    "doc_type": result.doc_type,
                    "language": result.language
                }
            )
            
            return result.model_dump()
            
        except Exception as e:
            logger.error(
                "Internal document analysis step failed",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                }
            )
            raise

    async def _get_document_text(self, payload: DocumentAnalyzePayload) -> str:
        """Extract text from document payload with proper error handling."""
        text = (payload.text or "").strip()
        
        if not text and payload.file_url:
            try:
                file_bytes = await self._download_file_with_retry(
                    str(payload.file_url), 
                    service_token=payload.service_token
                )
                if len(file_bytes) > MAX_FILE_SIZE_BYTES:
                    raise FileValidationError(
                        f"File too large: {len(file_bytes)} bytes (max {MAX_FILE_SIZE_BYTES})",
                        file_size=len(file_bytes),
                        mime_type=payload.mime_type
                    )
                text = self._extract_text(file_bytes, payload.mime_type)
            except Exception as e:
                logger.error(
                    "Failed to process document file",
                    extra={
                        "document_id": payload.document_id,
                        "version_id": payload.version_id,
                        "error": str(e)
                    }
                )
                raise
        
        return text.strip()
    
    async def _validate_file_url(self, url: str) -> None:
        """Validate file URL format and accessibility."""
        if not url.startswith(('http://', 'https://')):
            raise FileValidationError(f"Invalid URL scheme: {url}")
        
        # Check URL length
        if len(url) > 2048:
            raise FileValidationError(f"URL too long: {len(url)} characters")
    
    async def _download_file_with_retry(self, url: str, service_token: str = None) -> bytes:
        """Download file with retry logic and proper error handling."""
        last_exception = None
        
        for attempt in range(DOWNLOAD_MAX_RETRIES):
            try:
                logger.info(
                    "Downloading file",
                    extra={
                        "url": url,
                        "attempt": attempt + 1,
                        "max_attempts": DOWNLOAD_MAX_RETRIES,
                        "has_service_token": bool(service_token)
                    }
                )
                
                headers = {
                    "User-Agent": "DockFlow-AIService/1.0",
                }
                
                if service_token:
                    headers["Authorization"] = f"Bearer {service_token}"
                
                async with httpx.AsyncClient(
                    timeout=DOWNLOAD_TIMEOUT, 
                    follow_redirects=True
                ) as client:
                    response = await client.get(url, headers=headers)
                    
                    if response.status_code == 401:
                        error_msg = f"Authentication failed (401): {response.text[:200] if response.text else 'No response body'}"
                        logger.error(
                            "Service token authentication failed - not retrying",
                            extra={
                                "url": url,
                                "status_code": 401,
                                "response": response.text[:200] if response.text else None
                            }
                        )
                        raise FileDownloadError(error_msg, url)
                    
                    response.raise_for_status()
                    
                    content = response.content
                    content_hash = hashlib.sha256(content).hexdigest()[:16]
                    
                    logger.info(
                        "File downloaded successfully",
                        extra={
                            "url": url,
                            "size_bytes": len(content),
                            "content_hash": content_hash
                        }
                    )
                    
                    return content
                    
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    raise FileDownloadError(f"Authentication failed (401): service token invalid or expired", url)
                last_exception = e
                logger.warning(
                    "File download attempt failed",
                    extra={
                        "url": url,
                        "attempt": attempt + 1,
                        "status_code": e.response.status_code,
                        "error": str(e)
                    }
                )
                
                if attempt < DOWNLOAD_MAX_RETRIES - 1:
                    await asyncio.sleep(2 ** attempt)
                    
            except httpx.HTTPError as e:
                last_exception = e
                logger.warning(
                    "File download attempt failed",
                    extra={
                        "url": url,
                        "attempt": attempt + 1,
                        "error": str(e)
                    }
                )
                
                if attempt < DOWNLOAD_MAX_RETRIES - 1:
                    await asyncio.sleep(2 ** attempt)
                
            except Exception as e:
                logger.error(
                    "Unexpected error during file download",
                    extra={
                        "url": url,
                        "error": str(e)
                    },
                    exc_info=True
                )
                raise FileDownloadError(f"Download failed: {str(e)}", url)
        
        raise FileDownloadError(
            f"Failed to download after {DOWNLOAD_MAX_RETRIES} attempts: {str(last_exception)}", 
            url
        )

    def _extract_text(self, content: bytes, mime_type: Optional[str]) -> str:
        mt = (mime_type or "").lower()

        # DOCX
        if "wordprocessingml.document" in mt or mt.endswith("docx"):
            return self._extract_docx(content)

        # PDF
        if mt == "application/pdf" or mt.endswith("pdf"):
            return self._extract_pdf(content)

        # fallback: пробуем как pdf, потом как docx
        try:
            t = self._extract_pdf(content)
            if t.strip():
                return t
        except Exception:
            pass

        try:
            return self._extract_docx(content)
        except Exception:
            return ""

    def _extract_docx(self, content: bytes) -> str:
        # python-docx принимает путь, но можно через BytesIO
        from io import BytesIO
        doc = Document(BytesIO(content))
        parts = []
        for p in doc.paragraphs:
            if p.text and p.text.strip():
                parts.append(p.text.strip())
        return "\n".join(parts)

    def _extract_pdf(self, content: bytes) -> str:
        from io import BytesIO
        reader = PdfReader(BytesIO(content))
        parts = []
        for page in reader.pages:
            t = page.extract_text() or ""
            t = t.strip()
            if t:
                parts.append(t)
        return "\n\n".join(parts)

    def _build_prompt(self, text: str) -> str:
        return (
            "You are DockFlow AI Analysis Engine.\n\n"
            "You are NOT a chatbot.\n"
            "You are NOT an assistant for end users.\n"
            "You are a backend analytical component inside a document workflow system.\n\n"
            "Your ONLY goal is to help the CORE SYSTEM:\n"
            "- understand the nature of the document,\n"
            "- detect risks, missing or unclear information,\n"
            "- decide how the document should move through the workflow.\n\n"
            "You must be conservative.\n"
            "If something is not explicitly stated in the document, mark it as \"unknown\".\n"
            "Never assume domain context, regulations, technologies, or dates unless they are clearly present.\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "STRICT OUTPUT RULES\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "1. Output ONLY valid JSON.\n"
            "2. No explanations, comments, or markdown.\n"
            "3. Do NOT invent facts.\n"
            "4. Prefer \"unknown\" over assumptions.\n"
            "5. Use simple, clear, non-marketing language.\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "ALLOWED DOCUMENT TYPES\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "- contract\n"
            "- instruction\n"
            "- policy\n"
            "- report\n"
            "- order\n"
            "- letter\n"
            "- technical documentation\n"
            "- specification\n"
            "- invoice\n"
            "- agreement\n"
            "- minutes\n"
            "- other\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "ALLOWED SYSTEM ROLES (STRICT)\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "Use ONLY these roles:\n"
            "- Worker\n"
            "- Manager\n"
            "- Legal\n"
            "- CEO\n"
            "- Director\n"
            "- Accounting\n"
            "- HR\n"
            "- Technical Lead\n"
            "If role cannot be determined, use \"unknown\".\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "ANALYSIS STEPS\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "STEP 1 — Document classification\n"
            "Classify the document using the allowed document types.\n"
            "If classification confidence is low, use \"other\".\n\n"
            "STEP 2 — Conservative semantic summary\n"
            "Describe:\n"
            "- purpose of the document\n"
            "- intended audience\n"
            "- required or expected actions\n\n"
            "Do NOT restate the title.\n"
            "Do NOT add context not found in the document.\n\n"
            "STEP 3 — Explicit requirements\n"
            "List ONLY actions or rules that are explicitly stated in the document.\n"
            "If none are explicit, return an empty list.\n\n"
            "STEP 4 — Recommendations\n"
            "List actions that are implied but not mandatory.\n"
            "If none are implied, return an empty list.\n\n"
            "STEP 5 — Risks & ambiguities\n"
            "Identify:\n"
            "- missing information\n"
            "- unclear responsibilities\n"
            "- vague instructions\n"
            "- outdated or unverifiable references (ONLY if clearly stated)\n\n"
            "Do NOT add risks based on general knowledge.\n\n"
            "STEP 6 — Workflow decision support\n"
            "Suggest how the CORE SYSTEM should handle this document.\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "OUTPUT JSON SCHEMA (STRICT)\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "{\n"
            '  "doc_type": "...",\n'
            '  "language": "ru | en | kz | unknown",\n'
            '  "semantic_summary": {\n'
            '    "purpose": "...",\n'
            '    "audience": "...",\n'
            '    "expected_actions": ["..."]\n'
            '  },\n'
            '  "requirements": ["..."],\n'
            '  "recommendations": ["..."],\n'
            '  "risks": [\n'
            '    {\n'
            '      "type": "...",\n'
            '      "description": "...",\n'
            '      "severity": "low | medium | high | unknown"\n'
            '    }\n'
            '  ],\n'
            '  "ambiguities": ["..."],\n'
            '  "workflow_decision": {\n'
            '    "suggested_reviewers": ["Worker | Manager | Legal | CEO | unknown"],\n'
            '    "approval_complexity": "single-step | multi-step | unknown",\n'
            '    "decision_flags": {\n'
            '      "can_auto_approve": true | false,\n'
            '      "requires_human_review": true | false,\n'
            '      "missing_mandatory_info": true | false\n'
            '    },\n'
            '    "analysis_confidence": 0.0\n'
            '  }\n'
            "}\n\n"
            "DOCUMENT:\n"
            f"{text}"
        )

    async def _generate_with_retry(self, prompt: str, llm: LlmClient, max_retries: int = 2) -> str:
        """Generate LLM response with retry logic."""
        last_error = None
        
        for attempt in range(max_retries + 1):
            try:
                logger.info(
                    "Generating LLM response",
                    extra={
                        "attempt": attempt + 1,
                        "max_attempts": max_retries + 1,
                        "prompt_length": len(prompt)
                    }
                )
                
                response = await llm.generate(prompt)
                
                logger.info(
                    "LLM response generated successfully",
                    extra={
                        "attempt": attempt + 1,
                        "response_length": len(response)
                    }
                )
                
                return response
                
            except Exception as e:
                last_error = e
                logger.warning(
                    "LLM generation attempt failed",
                    extra={
                        "attempt": attempt + 1,
                        "error": str(e),
                        "error_type": type(e).__name__
                    }
                )
                
                if attempt < max_retries:
                    # Brief delay before retry
                    await asyncio.sleep(0.5)
        
        # All retries exhausted
        raise LlmProcessingError(
            f"LLM generation failed after {max_retries + 1} attempts: {str(last_error)}",
            provider=getattr(llm, 'provider_name', 'unknown'),
            response=str(last_error)
        )
    
    def _safe_json_loads(self, s: str) -> dict:
        """Safely parse JSON from LLM response with enhanced error handling."""
        if not s or not s.strip():
            raise JsonParsingError("Empty response from LLM", s)
        
        # Clean the response - remove markdown code blocks
        cleaned = s.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]  # Remove ```json
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]  # Remove ```
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]  # Remove trailing ```
        
        cleaned = cleaned.strip()
        
        # Try direct parsing first
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # Try to fix single quotes if it looks like a python dict
        # (Be careful not to break legitimate single quotes inside strings)
        try:
            # Simple heuristic: if it contains 'key': but not "key":
            if "'" in cleaned and '"' not in cleaned:
                # This is risky but sometimes helps with low-quality models
                fixed = cleaned.replace("'", '"')
                return json.loads(fixed)
        except Exception:
            pass

        # Try to extract first valid JSON object using incremental parsing
        start = cleaned.find("{")
        if start != -1:
            decoder = json.JSONDecoder()
            # Try parsing from every '{' until success
            for i in range(len(cleaned)):
                if cleaned[i] == '{':
                    try:
                        result, _ = decoder.raw_decode(cleaned, i)
                        return result
                    except json.JSONDecodeError:
                        continue
            
            # Fallback: try finding matching braces
            depth = 0
            end = -1
            for i, c in enumerate(cleaned[start:], start):
                if c == '{':
                    depth += 1
                elif c == '}':
                    depth -= 1
                    if depth == 0:
                        end = i
                        break
            
            if end != -1:
                json_chunk = cleaned[start:end + 1]
                try:
                    return json.loads(json_chunk)
                except json.JSONDecodeError as e:
                    raise JsonParsingError(
                        f"Could not extract valid JSON from LLM response: {str(e)}",
                        cleaned
                    )

        raise JsonParsingError(
            "No valid JSON object found in LLM response",
            cleaned
        )

    async def review(self, payload: dict) -> dict:
        """
        Perform a specialized document review focusing on weaknesses and approval suggestions.
        """
        try:
            p = DocumentReviewPayload.model_validate(payload)
            logger.info("Starting document review", extra={"document_id": p.document_id, "topic": p.topic})
            
            text = await self._get_document_text(p)
            if not text.strip():
                return DocumentReviewResult(
                    recommendation="Cannot review empty document.",
                    approval_suggestion="unknown"
                ).model_dump()

            if len(text) > MAX_TEXT_CHARS:
                text = text[:MAX_TEXT_CHARS] + "\n\n[TRUNCATED]"

            prompt = self._build_review_prompt(text, p.topic)
            llm = self._llm_factory(p.provider) if p.provider else self._llm_factory()
            
            answer = await self._generate_with_retry(prompt, llm=llm)
            data = self._safe_json_loads(answer)
            result = DocumentReviewResult.model_validate(data)
            
            return result.model_dump()
        except Exception as e:
            logger.error("Document review failed", extra={"error": str(e)})
            raise

    def _build_review_prompt(self, text: str, topic: Optional[str]) -> str:
        topic_context = f"The review should specifically focus on this topic: {topic}" if topic else "Perform a general document review."
        
        return (
            "You are DockFlow AI Review Specialist.\n\n"
            "Your goal is to perform a deep analysis of the document to identify weaknesses, "
            "risks, and provide an approval recommendation.\n\n"
            f"{topic_context}\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "STRICT OUTPUT RULES\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "1. Output ONLY valid JSON.\n"
            "2. No explanations, comments, or markdown.\n"
            "3. Be critical. Look for contradictions, missing clauses, or vague language.\n"
            "4. Suggest an action for the reviewer (approve, reject, or request_changes).\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "OUTPUT JSON SCHEMA\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "{\n"
            '  "weaknesses": [\n'
            '    {\n'
            '      "title": "Short title of the issue",\n'
            '      "description": "Detailed explanation of why this is a weakness",\n'
            '      "topic_relevance": "How this relates to the requested topic",\n'
            '      "severity": "low | medium | high | unknown"\n'
            '    }\n'
            '  ],\n'
            '  "recommendation": "Overall summary and advice for the human reviewer",\n'
            '  "approval_suggestion": "approve | reject | request_changes | unknown",\n'
            '  "confidence": 0.0\n'
            "}\n\n"
            "DOCUMENT:\n"
            f"{text}"
        )
