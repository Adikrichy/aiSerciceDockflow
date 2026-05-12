import logging
import json
from typing import Any
from app.schemas.messages import ReportInsightsPayload, ReportInsightsResult
from app.llm.client import LlmClient

logger = logging.getLogger(__name__)

class ReportInsightsService:
    def __init__(self, llm_factory):
        self._llm_factory = llm_factory

    async def get_insights(self, payload: dict) -> dict:
        try:
            p = ReportInsightsPayload.model_validate(payload)
            logger.info(f"Generating insights for company {p.company_id}, range: {p.time_range}")
            
            # Format report data for prompt
            report_summary = self._format_report_data(p.report_data)
            
            prompt = self._build_prompt(report_summary, p.time_range)
            
            # Select LLM provider
            llm = self._llm_factory(p.provider) if p.provider else self._llm_factory()
            
            answer = await llm.generate(prompt)
            
            # Extract insights from response (expected plain text or simple JSON)
            # We'll try to extract plain text if possible, or parse if it's JSON
            insights_text = self._parse_insights(answer)
            
            result = ReportInsightsResult(insights=insights_text)
            return result.model_dump()
            
        except Exception as e:
            logger.error(f"Failed to generate report insights: {str(e)}", exc_info=True)
            raise

    def _format_report_data(self, data: dict) -> str:
        """Converts report data dict to a readable string for the LLM."""
        summary = []
        summary.append(f"- Total Documents: {data.get('totalDocuments', 0)}")
        summary.append(f"- Total Versions (Edits): {data.get('totalVersions', 0)}")
        summary.append(f"- Pending Documents: {data.get('pendingDocuments', 0)}")
        summary.append(f"- Approved Documents: {data.get('approvedDocuments', 0)}")
        summary.append(f"- Rejected Documents: {data.get('rejectedDocuments', 0)}")
        summary.append(f"- Average Processing Time: {data.get('averageProcessingTime', 0)} hours")
        summary.append(f"- Active Users: {data.get('activeUsers', 0)}")
        
        # Add contributors if available
        contributors = data.get('userActivity', [])
        if contributors:
            summary.append("\nTop Contributors:")
            for c in contributors[:5]: # Top 5
                summary.append(f"  * {c.get('userName', 'Unknown')}: {c.get('documentCount', 0)} docs, {c.get('avgProcessingTime', 0)}h avg speed")
        
        # Add document types if available
        types = data.get('documentTypes', [])
        if types:
            summary.append("\nDocument Distribution:")
            for t in types:
                summary.append(f"  * {t.get('type', 'Other')}: {t.get('count', 0)}")
                
        return "\n".join(summary)

    def _build_prompt(self, report_summary: str, time_range: str) -> str:
        return (
            "You are DockFlow Business Intelligence Assistant.\n"
            "Your task is to analyze the following document management system report and provide high-level insights.\n\n"
            f"REPORT PERIOD: {time_range}\n"
            "METRICS:\n"
            f"{report_summary}\n\n"
            "INSTRUCTIONS:\n"
            "1. Be concise but professional.\n"
            "2. Identify bottlenecks (e.g., long processing time, high rejection rate).\n"
            "3. Highlight top performance (e.g., most active users).\n"
            "4. Provide 2-3 actionable recommendations to improve workflow efficiency.\n"
            "5. Detect trends if possible (e.g., 'Document load is increasing').\n"
            "6. Output your analysis in a friendly, business-oriented tone.\n"
            "7. IMPORTANT: Output ONLY the analysis text. Do not use JSON or markdown code blocks unless requested.\n"
            "8. LANGUAGE: Respond in the language most appropriate for the user (default to Russian if unsure, or follow the dominant language of the data labels).\n"
        )

    def _parse_insights(self, answer: str) -> str:
        # Clean answer from common LLM wrappers
        cleaned = answer.strip()
        if cleaned.startswith("```"):
            # If AI wrapped it in markdown, try to strip it
            lines = cleaned.split("\n")
            if len(lines) > 2 and lines[0].startswith("```"):
                cleaned = "\n".join(lines[1:-1])
        
        # If it looks like JSON, try to extract the message field if it exists
        try:
            data = json.loads(cleaned)
            if isinstance(data, dict):
                return data.get("insights", data.get("analysis", data.get("response", cleaned)))
        except:
            pass
            
        return cleaned
