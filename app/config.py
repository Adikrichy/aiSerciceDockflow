from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = Field(default="AI Service")
    app_env: str = Field(default="dev")  # dev/prod
    log_level: str = Field(default="INFO")

    # RabbitMQ (Windows local)
    rabbitmq_url: str = Field(default="amqp://guest:guest@localhost:5672/")
    rabbitmq_queue_in: str = Field(default="ai_tasks")
    rabbitmq_queue_out: str = Field(default="dockflow.core.ai_results")

    # LLM Providers Configuration
    llm_provider: str = Field(default="mock")  # mock/gemini/groq/ollama
    
    # Gemini API
    gemini_api_key: str | None = Field(default=None)
    gemini_model: str = Field(default="gemini-pro")
    
    # Groq API
    groq_api_key: str | None = Field(default=None)
    groq_model: str = Field(default="mixtral-8x7b-32768")
    
    # Ollama Local
    ollama_base_url: str = Field(default="http://localhost:11434")
    ollama_model: str = Field(default="llama2")

    rabbitmq_retry_queue: str = Field(default="ai_tasks.retry")
    rabbitmq_dlq: str = Field(default="ai_tasks.dlq")
    rabbitmq_retry_delay_ms: int = Field(default=5000)
    rabbitmq_max_retries: int = Field(default=5)


settings = Settings()
