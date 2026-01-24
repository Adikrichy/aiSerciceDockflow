import sys
import os

# Add the project root to sys.path
sys.path.append(os.getcwd())

from app.schemas.messages import DocumentAnalyzeResult

# Test data inspired by the error report
test_data = {
    "doc_type": "technical documentation",
    "language": "ru",
    "semantic_summary": {
        "purpose": "Test implementation",
        "audience": "Developers",
        "expected_actions": ["Review code"]
    },
    "requirements": [],
    "recommendations": [],
    "risks": [],
    "ambiguities": [],
    "workflow_decision": {
        "suggested_reviewers": ["Worker", "Technical Lead", "Hallucinated Role"],
        "approval_complexity": "single-step",
        "decision_flags": {
            "can_auto_approve": False,
            "requires_human_review": True,
            "missing_mandatory_info": False
        },
        "analysis_confidence": 0.95
    }
}

try:
    result = DocumentAnalyzeResult.model_validate(test_data)
    print("✅ Validation successful!")
    print(f"Doc type: {result.doc_type}")
    print(f"Reviewers: {result.workflow_decision.suggested_reviewers}")
    
    # Test fallback
    test_data_fallback = test_data.copy()
    test_data_fallback["doc_type"] = "some crazy hallucination"
    result_fallback = DocumentAnalyzeResult.model_validate(test_data_fallback)
    print(f"\n✅ Fallback test successful!")
    print(f"Hallucinated doc type mapped to: {result_fallback.doc_type}")
    
except Exception as e:
    print(f"❌ Validation failed: {e}")
    sys.exit(1)
