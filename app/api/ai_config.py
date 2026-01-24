from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
from typing import List, Optional
from app.config import settings
from app.llm.client import create_llm_client
import os
import asyncio

router = APIRouter(prefix="/ai", tags=["AI Configuration"])

class ProviderConfig(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    provider: str
    api_key: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None

class ProviderStatus(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    provider: str
    is_available: bool
    error_message: Optional[str] = None

class CurrentConfig(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    current_provider: str
    available_providers: List[str]
    provider_configs: dict

# Available providers
AVAILABLE_PROVIDERS = ["mock", "gemini", "groq", "ollama"]

@router.get("/providers")
async def get_available_providers():
    """Get list of available AI providers"""
    return {"providers": AVAILABLE_PROVIDERS}

@router.get("/config")
async def get_current_config():
    """Get current AI configuration"""
    configs = {}
    
    # Get current environment values
    configs["mock"] = {"enabled": True}
    configs["gemini"] = {
        "api_key_set": bool(settings.gemini_api_key),
        "model": settings.gemini_model
    }
    configs["groq"] = {
        "api_key_set": bool(settings.groq_api_key),
        "model": settings.groq_model
    }
    configs["ollama"] = {
        "base_url": settings.ollama_base_url,
        "model": settings.ollama_model
    }
    
    return CurrentConfig(
        current_provider=settings.llm_provider,
        available_providers=AVAILABLE_PROVIDERS,
        provider_configs=configs
    )

@router.post("/provider/{provider}")
async def set_provider(provider: str, config: ProviderConfig = None):
    """Set the active AI provider"""
    if provider not in AVAILABLE_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Invalid provider. Available: {AVAILABLE_PROVIDERS}")
    
    try:
        # Test the provider by creating a client
        test_client = create_llm_client(provider)
        
        # Update environment variable
        os.environ["LLM_PROVIDER"] = provider
        
        # Update settings (this won't persist after restart, but it's good for runtime changes)
        settings.llm_provider = provider
        
        return {
            "message": f"Provider switched to {provider}",
            "provider": provider,
            "status": "success"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cannot initialize provider {provider}: {str(e)}")

@router.post("/test-provider/{provider}")
async def test_provider(provider: str):
    """Test if a provider is working"""
    if provider not in AVAILABLE_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Invalid provider. Available: {AVAILABLE_PROVIDERS}")
    
    try:
        client = create_llm_client(provider)
        # Test with a simple prompt
        test_prompt = "Say 'Hello, this is a test!'"
        response = await client.generate(test_prompt)
        
        return {
            "provider": provider,
            "status": "working",
            "test_response": response[:100],  # First 100 chars
            "can_generate": True
        }
    except Exception as e:
        return {
            "provider": provider,
            "status": "error",
            "error": str(e),
            "can_generate": False
        }

@router.get("/status")
async def get_provider_status():
    """Get status of all providers in parallel"""
    
    async def get_single_status(provider: str):
        try:
            client = create_llm_client(provider)
            # Quick test with 5s timeout
            test_prompt = "test"
            await asyncio.wait_for(client.generate(test_prompt), timeout=5.0)
            return ProviderStatus(
                provider=provider,
                is_available=True
            )
        except Exception as e:
            return ProviderStatus(
                provider=provider,
                is_available=False,
                error_message=str(e)
            )

    tasks = [get_single_status(p) for p in AVAILABLE_PROVIDERS]
    statuses = await asyncio.gather(*tasks)
    
    return {"providers": statuses}