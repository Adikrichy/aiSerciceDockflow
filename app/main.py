from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.health import router as health_router
from app.api.ai_config import router as ai_config_router
from app.llm.client import create_llm_client
from app.services.document_ai import DocumentAiService
from app.services.workflow_ai import WorkflowAiService
from app.services.router import TaskRouter
from app.producers.rabbit_producer import RabbitProducer
from app.consumers.rabbit_consumer import RabbitConsumer

app = FastAPI(title=settings.app_name, version="0.3.0")

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

app.include_router(health_router)
app.include_router(ai_config_router)

document_service = DocumentAiService(create_llm_client)
workflow_service = WorkflowAiService(create_llm_client)

router = TaskRouter(document_service=document_service, workflow_service=workflow_service)

producer = RabbitProducer()
consumer = RabbitConsumer(producer=producer, router=router)


@app.on_event("startup")
async def startup():
    await producer.start()
    await consumer.start()


@app.on_event("shutdown")
async def shutdown():
    await consumer.stop()
    await producer.stop()
