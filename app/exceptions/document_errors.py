"""Custom exceptions for document analysis service."""

from typing import Optional


class DocumentAnalysisError(Exception):
    """Base exception for document analysis errors."""
    def __init__(self, message: str, error_code: str = "UNKNOWN_ERROR", details: Optional[dict] = None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)


class FileDownloadError(DocumentAnalysisError):
    """Raised when file download fails."""
    def __init__(self, message: str, url: str, status_code: Optional[int] = None):
        details = {"url": url}
        if status_code:
            details["status_code"] = status_code
        super().__init__(message, "FILE_DOWNLOAD_ERROR", details)


class FileValidationError(DocumentAnalysisError):
    """Raised when file validation fails."""
    def __init__(self, message: str, file_size: Optional[int] = None, mime_type: Optional[str] = None):
        details = {}
        if file_size is not None:
            details["file_size"] = file_size
        if mime_type:
            details["mime_type"] = mime_type
        super().__init__(message, "FILE_VALIDATION_ERROR", details)


class TextExtractionError(DocumentAnalysisError):
    """Raised when text extraction fails."""
    def __init__(self, message: str, mime_type: str):
        super().__init__(message, "TEXT_EXTRACTION_ERROR", {"mime_type": mime_type})


class LlmProcessingError(DocumentAnalysisError):
    """Raised when LLM processing fails."""
    def __init__(self, message: str, provider: str, response: Optional[str] = None):
        details = {"provider": provider}
        if response:
            details["response_snippet"] = response[:200] + "..." if len(response) > 200 else response
        super().__init__(message, "LLM_PROCESSING_ERROR", details)


class JsonParsingError(DocumentAnalysisError):
    """Raised when JSON parsing fails."""
    def __init__(self, message: str, raw_response: str):
        super().__init__(
            message, 
            "JSON_PARSING_ERROR", 
            {"response_length": len(raw_response)}
        )


class DocumentNotFoundError(DocumentAnalysisError):
    """Raised when document is not found."""
    def __init__(self, document_id: int, version_id: int):
        super().__init__(
            f"Document {document_id} version {version_id} not found",
            "DOCUMENT_NOT_FOUND",
            {"document_id": document_id, "version_id": version_id}
        )