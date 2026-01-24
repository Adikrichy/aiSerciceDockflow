#!/usr/bin/env python3
"""
Test script for AI service providers
"""

import asyncio
import sys
import os

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.llm.client import create_llm_client

async def test_provider(provider_name: str):
    """Test a specific AI provider"""
    print(f"\n--- Testing {provider_name.upper()} ---")
    
    try:
        client = create_llm_client(provider_name)
        print(f"✓ Client created successfully")
        
        # Test prompt
        prompt = "Summarize this in one sentence: Artificial Intelligence is transforming how we work and live."
        print(f"Sending prompt: {prompt[:50]}...")
        
        response = await client.generate(prompt)
        print(f"Response: {response}")
        print(f"✓ {provider_name} is working!")
        return True
        
    except Exception as e:
        print(f"✗ {provider_name} failed: {str(e)}")
        return False

async def main():
    """Test all available providers"""
    print("Testing AI Service Providers")
    print("=" * 40)
    
    providers = ["mock", "gemini", "groq", "ollama"]
    results = {}
    
    for provider in providers:
        try:
            results[provider] = await test_provider(provider)
        except Exception as e:
            print(f"✗ {provider} test failed with exception: {str(e)}")
            results[provider] = False
    
    print("\n" + "=" * 40)
    print("SUMMARY:")
    for provider, success in results.items():
        status = "✓ WORKING" if success else "✗ FAILED"
        print(f"{provider:10} : {status}")

if __name__ == "__main__":
    asyncio.run(main())