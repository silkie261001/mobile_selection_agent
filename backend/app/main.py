"""
FastAPI application for the Mobile Shopping Chat Agent.
"""
import os
import uuid
import logging
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from .agent.agent_builder import get_agent, ShoppingAgent
from .data.phone_service import phone_service


# Configure logging
def setup_logging():
    """Configure logging for the application."""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_format = os.getenv(
        "LOG_FORMAT",
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format=log_format,
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

    # Set specific loggers
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    return logging.getLogger(__name__)


logger = setup_logging()


# Request/Response models
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    session_id: str
    phones: list[dict]
    type: str


class PhoneSearchRequest(BaseModel):
    query: Optional[str] = None
    brand: Optional[str] = None
    min_price: Optional[int] = None
    max_price: Optional[int] = None
    limit: int = 10


# Agent instance
agent: ShoppingAgent = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    global agent
    logger.info("Starting Mobile Shopping Agent...")

    try:
        agent = get_agent()
        logger.info("Agent initialized successfully!")
    except Exception as e:
        logger.error(f"Failed to initialize agent: {e}", exc_info=True)

    yield

    logger.info("Shutting down...")


# Create FastAPI app
app = FastAPI(
    title="Mobile Shopping Chat Agent",
    description="AI-powered shopping assistant for mobile phones",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "Mobile Shopping Chat Agent",
        "version": "1.0.0"
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Chat with the shopping agent.

    Send a message and receive a response with optional phone recommendations.
    """
    if not agent:
        logger.error("Chat request received but agent not initialized")
        raise HTTPException(status_code=503, detail="Agent not initialized")

    if not request.message or not request.message.strip():
        logger.warning("Empty message received")
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    # Generate session ID if not provided
    session_id = request.session_id or str(uuid.uuid4())
    logger.info(f"Processing chat request - session: {session_id}, message: {request.message[:100]}...")

    try:
        result = await agent.chat(request.message, session_id)
        logger.info(f"Chat response generated - session: {session_id}, type: {result['type']}, phones: {len(result['phones'])}")
        return ChatResponse(
            response=result["response"],
            session_id=session_id,
            phones=result["phones"],
            type=result["type"]
        )
    except Exception as e:
        logger.error(f"Chat error - session: {session_id}, error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to process message")


@app.post("/api/chat/clear")
async def clear_chat(session_id: str):
    """Clear chat history for a session."""
    if agent:
        agent.clear_history(session_id)
    return {"status": "cleared", "session_id": session_id}


@app.get("/api/phones")
async def get_phones(
    query: Optional[str] = None,
    brand: Optional[str] = None,
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    limit: int = 20
):
    """
    Get phones with optional filters.

    This is a direct database query, not using the AI agent.
    """
    phones = phone_service.search_phones(
        query=query,
        brand=brand,
        min_price=min_price,
        max_price=max_price,
        limit=limit
    )
    return {"phones": phones, "count": len(phones)}


@app.get("/api/phones/{phone_id}")
async def get_phone(phone_id: str):
    """Get details of a specific phone."""
    phone = phone_service.get_phone_by_id(phone_id)
    if not phone:
        phone = phone_service.get_phone_by_name(phone_id)

    if not phone:
        raise HTTPException(status_code=404, detail="Phone not found")

    return phone


@app.get("/api/phones/compare")
async def compare_phones(phones: str):
    """
    Compare multiple phones.

    Args:
        phones: Comma-separated list of phone IDs or names
    """
    phone_list = [p.strip() for p in phones.split(",")]
    if len(phone_list) < 2:
        raise HTTPException(status_code=400, detail="Please provide at least 2 phones to compare")

    result = phone_service.compare_phones(phone_list)
    if len(result) < 2:
        raise HTTPException(status_code=404, detail="Could not find enough phones to compare")

    return {
        "phones": result,
        "comparison_table": phone_service.format_comparison_table(result)
    }


@app.get("/api/brands")
async def get_brands():
    """Get all available brands."""
    return {"brands": phone_service.get_available_brands()}


@app.get("/api/recommendations/camera")
async def get_camera_recommendations(max_price: Optional[int] = None, limit: int = 5):
    """Get best camera phone recommendations."""
    phones = phone_service.get_best_camera_phones(max_price=max_price, limit=limit)
    return {"phones": phones, "category": "camera"}


@app.get("/api/recommendations/battery")
async def get_battery_recommendations(max_price: Optional[int] = None, limit: int = 5):
    """Get best battery phone recommendations."""
    phones = phone_service.get_best_battery_phones(max_price=max_price, limit=limit)
    return {"phones": phones, "category": "battery"}


@app.get("/api/recommendations/gaming")
async def get_gaming_recommendations(max_price: Optional[int] = None, limit: int = 5):
    """Get best gaming phone recommendations."""
    phones = phone_service.get_gaming_phones(max_price=max_price, limit=limit)
    return {"phones": phones, "category": "gaming"}


@app.get("/api/recommendations/compact")
async def get_compact_recommendations(max_price: Optional[int] = None, limit: int = 5):
    """Get compact phone recommendations."""
    phones = phone_service.get_compact_phones(max_price=max_price, limit=limit)
    return {"phones": phones, "category": "compact"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
