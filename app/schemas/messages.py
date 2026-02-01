from __future__ import annotations

import pydantic
from pydantic import BaseModel, Field, HttpUrl
from typing import Any, Literal, Optional
from uuid import uuid4
from datetime import datetime, timezone


TaskType = Literal["DOCUMENT_ANALYZE", "WORKFLOW_SUGGEST", "PING", "CHAT", "DOCUMENT_REVIEW"]
TaskStatus = Literal["OK", "SUCCESS", "ERROR", "PROCESSING", "CHAT_RESPONSE"]

DockType = Literal[
    "contract", "instruction", "policy", "report", "order", "letter", 
    "technical documentation", "specification", "invoice", "agreement", "minutes", "other"
]
LangType = Literal["ru", "en", "kz", "unknown"]
SystemRole = Literal["Worker", "Manager", "Legal", "CEO", "Director", "Accounting", "HR", "Technical Lead", "unknown"]
RiskSeverity = Literal["low", "medium", "high", "unknown"]


class Envelope(BaseModel):
    schema_version: int = 1
    correlation_id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class DocumentAnalyzePayload(BaseModel):
    document_id: int
    version_id: int

    file_url: Optional[HttpUrl] = None
    service_token: Optional[str] = None
    mime_type: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    checksum: Optional[str] = None

    priority: str = "normal"

    text: Optional[str] = None
    provider: Optional[str] = None


class ChatPayload(BaseModel):
    content: str
    channel_id: int
    sender_id: int
    sender_name: str
    document_id: Optional[int] = None
    version_id: Optional[int] = None
    file_url: Optional[HttpUrl] = None
    service_token: Optional[str] = None
    mime_type: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    chat_type: Literal["GENERAL", "DOCUMENT"] = "GENERAL"
    history: list[dict[str, Any]] = Field(default_factory=list)
    context: Optional[dict[str, Any]] = None


class ChatResult(BaseModel):
    response: str
    channel_id: int
    used_model: Optional[str] = None


class SemanticSummary(BaseModel):
    purpose: str
    audience: str
    expected_actions: list[str] = Field(default_factory=list)


class RiskItem(BaseModel):
    type: str
    description: str
    severity: RiskSeverity


class WorkflowDecisionFlags(BaseModel):
    can_auto_approve: bool
    requires_human_review: bool
    missing_mandatory_info: bool


class WorkflowDecision(BaseModel):
    suggested_reviewers: list[SystemRole] = Field(default_factory=list)
    approval_complexity: Literal["single-step", "multi-step", "unknown"]
    decision_flags: WorkflowDecisionFlags
    analysis_confidence: float

    @pydantic.field_validator("suggested_reviewers", mode="before")
    @classmethod
    def normalize_suggested_reviewers(cls, v: Any):
        """
        LLM sometimes sends a string instead of a list: "unknown".
        Or it sends roles that are not in our Literal.
        We normalize and filter here to avoid ValidationError.
        """
        if v is None:
            return []
        
        # Convert single string to list
        raw_list = []
        if isinstance(v, str):
            s = v.strip()
            if s.lower() in {"unknown", "n/a", "none", ""}:
                return []
            raw_list = [s]
        elif isinstance(v, list):
            raw_list = v
        else:
            return []

        allowed = {
            "Worker", "Manager", "Legal", "CEO", 
            "Director", "Accounting", "HR", "Technical Lead", "unknown"
        }
        
        mapping_lower = {role.lower(): role for role in allowed}
        
        out: list[str] = []
        for item in raw_list:
            if not isinstance(item, str):
                continue
            
            val = item.strip()
            if not val:
                continue
                
            # Exact match
            if val in allowed:
                out.append(val)
                continue
                
            # Case-insensitive match or fallback to unknown
            normalized = mapping_lower.get(val.lower())
            if normalized:
                out.append(normalized)
            else:
                out.append("unknown")
                
        # Remove duplicates and return
        return list(dict.fromkeys(out))

    @pydantic.field_validator("analysis_confidence", mode="before")
    @classmethod
    def normalize_confidence(cls, v: Any) -> float:
        """
        Sometimes the model sends confidence as a string. Convert it.
        And clamp 0..1.
        """
        try:
            val = float(v)
        except (TypeError, ValueError):
            return 0.0
        if val < 0.0:
            return 0.0
        if val > 1.0:
            return 1.0
        return val


class DocumentAnalyzeResult(BaseModel):
    doc_type: DockType
    language: LangType
    semantic_summary: SemanticSummary
    requirements: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    risks: list[RiskItem] = Field(default_factory=list)
    ambiguities: list[str] = Field(default_factory=list)
    workflow_decision: WorkflowDecision

    @pydantic.field_validator("doc_type", mode="before")
    @classmethod
    def normalize_doc_type(cls, v: Any) -> str:
        """
        Normalize doc_type and fallback to 'other' if unknown.
        """
        if not isinstance(v, str):
            return "other"
            
        val = v.strip().lower()
        allowed_map = {
            "contract": "contract",
            "instruction": "instruction",
            "policy": "policy",
            "report": "report",
            "order": "order",
            "letter": "letter",
            "technical documentation": "technical documentation",
            "specification": "specification",
            "invoice": "invoice",
            "agreement": "agreement",
            "minutes": "minutes",
            "other": "other"
        }
        
        # Try to find a match in the keys
        return allowed_map.get(val, "other")

    @pydantic.field_validator("language", mode="before")
    @classmethod
    def normalize_language(cls, v: Any) -> str:
        if not isinstance(v, str):
            return "unknown"
        val = v.lower().strip()
        mapping = {
            "english": "en",
            "russian": "ru",
            "kazakh": "kz",
            "русский": "ru",
            "английский": "en",
            "казахский": "kz",
            "ru": "ru",
            "en": "en",
            "kz": "kz",
        }
        return mapping.get(val, "unknown")


class DocumentReviewPayload(DocumentAnalyzePayload):
    topic: Optional[str] = None


class DocumentWeakness(BaseModel):
    title: str
    description: str
    topic_relevance: str
    severity: RiskSeverity


class DocumentReviewResult(BaseModel):
    weaknesses: list[DocumentWeakness] = Field(default_factory=list)
    recommendation: str
    approval_suggestion: Literal["approve", "reject", "request_changes", "unknown"]
    confidence: float = 0.0


class AiTask(Envelope):
    task_id: str = Field(default_factory=lambda: str(uuid4()))
    type: TaskType
    payload: dict[str, Any] = Field(default_factory=dict)

    # куда слать ответ (можно переопределять с Core)
    reply_to: str | None = None


class AiResult(Envelope):
    task_id: str
    status: TaskStatus
    result: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
