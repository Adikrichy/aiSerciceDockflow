# AI Service Documentation

## Overview
This service provides AI capabilities for the DocFlow system with support for multiple AI providers.

## Supported Providers

### 1. Mock Provider (Default)
- **Purpose**: Development and testing
- **Requirements**: None
- **Configuration**: `LLM_PROVIDER=mock`

### 2. Google Gemini
- **Purpose**: Production-grade AI with Google's models
- **Requirements**: Google Cloud API key
- **Models**: `gemini-pro` (default)
- **Configuration**:
  ```
  LLM_PROVIDER=gemini
  GEMINI_API_KEY=your_api_key_here
  GEMINI_MODEL=gemini-pro
  ```

### 3. Groq
- **Purpose**: Fast inference with open-source models
- **Requirements**: Groq API key
- **Models**: `mixtral-8x7b-32768` (default)
- **Configuration**:
  ```
  LLM_PROVIDER=groq
  GROQ_API_KEY=your_api_key_here
  GROQ_MODEL=mixtral-8x7b-32768
  ```

### 4. Ollama (Local)
- **Purpose**: Private, offline AI with local models
- **Requirements**: Ollama running locally
- **Models**: `llama2` (default)
- **Configuration**:
  ```
  LLM_PROVIDER=ollama
  OLLAMA_BASE_URL=http://localhost:11434
  OLLAMA_MODEL=llama2
  ```

## Setup Instructions

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
Copy `.env.example` to `.env` and configure your preferred provider:

```bash
# For Gemini
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_google_api_key

# For Groq  
LLM_PROVIDER=groq
GROQ_API_KEY=your_groq_api_key

# For Ollama
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
```

### 3. Run the Service
```bash
uvicorn app.main:app --reload --port 8000
```

## API Endpoints

### Health Check
```
GET /health
```

### AI Configuration
```
GET /ai/providers          # List available providers
GET /ai/config            # Get current configuration
GET /ai/status            # Test all providers
POST /ai/provider/{name}  # Switch active provider
POST /ai/test-provider/{name}  # Test specific provider
```

## Testing

Run the test script to verify all providers:
```bash
python test_ai_providers.py
```

## Usage Examples

### Python Client
```python
from app.llm.client import create_llm_client

# Create client (uses configured provider)
client = create_llm_client()

# Generate response
response = await client.generate("Summarize this document...")
```

### API Usage
```bash
# Test current provider
curl -X POST "http://localhost:8000/ai/test-provider/gemini"

# Switch provider
curl -X POST "http://localhost:8000/ai/provider/groq"
```

## Provider Setup Details

### Google Gemini Setup
1. Go to [Google AI Studio](https://aistudio.google.com/)
2. Create an API key
3. Add to `.env`: `GEMINI_API_KEY=your_key`

### Groq Setup
1. Go to [Groq Console](https://console.groq.com/)
2. Create an API key
3. Add to `.env`: `GROQ_API_KEY=your_key`

### Ollama Setup
1. Install Ollama: `curl https://ollama.ai/install.sh | sh`
2. Pull a model: `ollama pull llama2`
3. Start Ollama: `ollama serve`
4. Service will auto-detect at `http://localhost:11434`

## Error Handling
- Invalid provider configurations will raise clear error messages
- Connection timeouts are handled gracefully
- Fallback to mock provider if real providers fail
- Detailed logging for debugging

## Performance Notes
- Gemini: ~1-2 seconds per request
- Groq: ~0.5-1 second per request  
- Ollama: Variable based on hardware (2-10 seconds)
- Mock: Instantaneous