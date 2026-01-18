"""
FastAPI application for the Mobile Shopping Chat Agent.
"""
import os
import uuid
import json
import logging
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

from agent.agent_builder import get_agent, ShoppingAgent


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


@app.get("/api/chat/stream")
async def chat_stream(
    message: str = Query(..., description="The user's message"),
    session_id: Optional[str] = Query(None, description="Session ID for conversation continuity")
):
    """
    Stream chat responses with real-time LLM-generated status updates.

    Uses Server-Sent Events (SSE) to stream:
    - status: LLM-generated thinking/progress messages
    - complete: Final response with phone recommendations
    """
    if not agent:
        logger.error("Stream request received but agent not initialized")
        raise HTTPException(status_code=503, detail="Agent not initialized")

    if not message or not message.strip():
        logger.warning("Empty message received")
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    # Generate session ID if not provided
    sid = session_id or str(uuid.uuid4())
    logger.info(f"Processing stream request - session: {sid}, message: {message[:100]}...")

    async def event_generator():
        """Generate SSE events from the agent stream."""
        try:
            async for event in agent.chat_stream(message, sid):
                # Format as SSE
                event_data = json.dumps({
                    **event,
                    "session_id": sid
                })
                yield f"data: {event_data}\n\n"
        except Exception as e:
            logger.error(f"Stream error - session: {sid}, error: {e}", exc_info=True)
            error_event = json.dumps({
                "type": "complete",
                "response": "I encountered an error. Please try again.",
                "phones": [],
                "response_type": "error",
                "session_id": sid
            })
            yield f"data: {error_event}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
