"""Tests for document analysis service with enhanced error handling."""

import pytest
from unittest.mock import AsyncMock, patch

from app.exceptions.document_errors import (
    FileDownloadError,
    FileValidationError,
    JsonParsingError
)
from app.services.document_ai import DocumentAiService
from app.schemas.messages import DocumentAnalyzePayload


@pytest.fixture
def mock_llm():
    llm = AsyncMock()
    llm.provider_name = "test_provider"
    return llm


@pytest.fixture
def service(mock_llm):
    return DocumentAiService(llm=mock_llm)


class TestDocumentValidation:
    """Test file validation logic."""

    def test_validate_large_file_raises_error(self, service):
        """Test that files larger than limit raise validation error."""
        payload_dict = {
            "document_id": 123,
            "version_id": 456,
            "file_url": "https://example.com/large.pdf",
            "file_size": 60 * 1024 * 1024,  # 60MB - exceeds 50MB limit
            "mime_type": "application/pdf"
        }
        
        with patch.object(service, '_download_file_with_retry', return_value=b'test') as mock_download:
            with patch.object(service, '_extract_text', return_value='test text'):
                with pytest.raises(FileValidationError) as exc_info:
                    import asyncio
                    asyncio.run(service.analyze(payload_dict))
                
                assert "File too large" in str(exc_info.value)
                assert exc_info.value.details["file_size"] == 60 * 1024 * 1024

    def test_invalid_url_scheme_raises_error(self, service):
        """Test that invalid URL schemes are rejected."""
        payload_dict = {
            "document_id": 123,
            "version_id": 456,
            "file_url": "ftp://invalid.com/file.pdf"  # Invalid scheme
        }
        
        with pytest.raises(FileValidationError) as exc_info:
            import asyncio
            asyncio.run(service.analyze(payload_dict))
        
        assert "Invalid URL scheme" in str(exc_info.value)


class TestErrorHandling:
    """Test error handling scenarios."""

    @pytest.mark.asyncio
    async def test_download_failure_propagates_error(self, service):
        """Test that download failures are properly handled."""
        payload_dict = {
            "document_id": 123,
            "version_id": 456,
            "file_url": "https://example.com/file.pdf"
        }
        
        with patch.object(service, '_download_file_with_retry', side_effect=FileDownloadError("Network error", "https://example.com/file.pdf")):
            with pytest.raises(FileDownloadError) as exc_info:
                await service.analyze(payload_dict)
            
            assert "Network error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_empty_document_returns_structured_result(self, service):
        """Test that empty documents return proper structured response."""
        payload_dict = {
            "document_id": 123,
            "version_id": 456,
            "text": ""  # Empty text
        }
        
        # Mock LLM to return valid JSON
        service._llm.generate = AsyncMock(return_value='{"doc_type": "other", "language": "unknown", "summary": [], "key_fields": {}, "risks": [], "notes": ["No text extracted"]}')
        
        result = await service.analyze(payload_dict)
        
        assert result["doc_type"] == "other"
        assert result["language"] == "unknown"
        assert "No text extracted" in result["notes"]

    @pytest.mark.asyncio
    async def test_json_parsing_error_handling(self, service):
        """Test handling of invalid JSON from LLM."""
        payload_dict = {
            "document_id": 123,
            "version_id": 456,
            "text": "Sample document text"
        }
        
        # Mock LLM to return invalid JSON
        service._llm.generate = AsyncMock(return_value='This is not JSON at all')
        
        with pytest.raises(JsonParsingError) as exc_info:
            await service.analyze(payload_dict)
        
        assert "No valid JSON object found" in str(exc_info.value)


class TestHappyPath:
    """Test successful processing scenarios."""

    @pytest.mark.asyncio
    async def test_successful_document_analysis(self, service):
        """Test complete successful document analysis flow."""
        payload_dict = {
            "document_id": 123,
            "version_id": 456,
            "text": "This is a contract between Company A and Company B for software development services worth $50,000.",
            "priority": "normal"
        }
        
        mock_response = '''{
            "doc_type": "contract",
            "language": "en",
            "summary": ["Software development contract for $50,000"],
            "key_fields": {
                "party_a": "Company A",
                "party_b": "Company B",
                "amount": "$50,000",
                "date": null,
                "term": null
            },
            "risks": [],
            "notes": ["Standard contract format"]
        }'''
        
        service._llm.generate = AsyncMock(return_value=mock_response)
        
        result = await service.analyze(payload_dict)
        
        assert result["doc_type"] == "contract"
        assert result["language"] == "en"
        assert len(result["summary"]) == 1
        assert result["key_fields"]["amount"] == "$50,000"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])