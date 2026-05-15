"""
FastAPI application — WhatsApp Government Schemes AI Agent.

Endpoints:
  GET  /webhook  — Meta webhook verification
  POST /webhook  — Incoming message handler
  GET  /health   — Health check
  POST /test     — Local testing endpoint (no WhatsApp needed)
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Query, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from fastapi.responses import PlainTextResponse, JSONResponse, StreamingResponse
from openai import AsyncOpenAI
import json

from app.config import settings
from app.data.store import init_db
from app.whatsapp.models import parse_webhook
from app.whatsapp.client import send_text_message, mark_as_read
from app.engine.state_machine import handle_message

# ──────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format="%(asctime)s │ %(levelname)-8s │ %(name)-30s │ %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# App lifecycle
# ──────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise database on startup."""
    logger.info("🚀 Starting Government Schemes AI Agent & Chat UI...")
    await init_db()
    logger.info("✅ Database ready")
    logger.info("✅ Agent is live (env=%s, port=%d)", settings.APP_ENV, settings.APP_PORT)
    yield
    logger.info("🛑 Shutting down...")


app = FastAPI(
    title="Government Schemes AI Agent",
    description="WhatsApp-based assistant & General Chat UI.",
    version="1.0.0",
    lifespan=lifespan,
)

# Mount ChatGPT clone UI at root
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# ──────────────────────────────────────────────
# ChatGPT Clone Chat Endpoint (POST)
# ──────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str
    content: str
class ChatRequest(BaseModel):
    messages: list[ChatMessage]

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    # ── Pre-flight check: is the API key configured? ──
    if not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY.startswith("sk-your"):
        async def no_key():
            msg = ("I'm not configured yet. Please add a valid OpenAI API key "
                   "to the `.env` file and restart the server.")
            yield f"data: {json.dumps({'content': msg})}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(no_key(), media_type="text/event-stream")

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    async def generate():
        try:
            stream = await client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[{"role": msg.role, "content": msg.content} for msg in request.messages],
                stream=True
            )
            async for chunk in stream:
                if chunk.choices and len(chunk.choices) > 0:
                    content = chunk.choices[0].delta.content
                    if content:
                        # Send JSON SSE
                        data = json.dumps({"content": content})
                        yield f"data: {data}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.error("Chat generation error: %s", str(e))
            error_str = str(e)
            # User-friendly messages for common API errors
            if "insufficient_quota" in error_str or "429" in error_str:
                friendly = ("⚠️ The AI service has run out of credits. "
                            "Please check your OpenAI billing at "
                            "platform.openai.com and add funds to continue.")
            elif "invalid_api_key" in error_str or "401" in error_str:
                friendly = ("⚠️ The API key is invalid. Please update it "
                            "in the `.env` file and restart the server.")
            elif "timeout" in error_str.lower():
                friendly = ("⚠️ The AI service took too long to respond. "
                            "Please try again in a moment.")
            else:
                friendly = ("⚠️ Something went wrong with the AI service. "
                            "Please try again later.")
            yield f"data: {json.dumps({'content': friendly})}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")

# ──────────────────────────────────────────────
# Webhook Verification (GET)
# ──────────────────────────────────────────────

@app.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    """
    Meta webhook verification endpoint.
    """
    logger.info("Webhook verification request: mode=%s", hub_mode)

    if hub_mode == "subscribe" and hub_verify_token == settings.WHATSAPP_VERIFY_TOKEN:
        logger.info("✅ Webhook verified successfully")
        return PlainTextResponse(content=hub_challenge, status_code=200)

    logger.warning("❌ Webhook verification failed (token mismatch)")
    raise HTTPException(status_code=403, detail="Verification failed")


# ──────────────────────────────────────────────
# Incoming Message Handler (POST)
# ──────────────────────────────────────────────

@app.post("/webhook")
async def handle_webhook(request: Request):
    """
    Receive and process incoming WhatsApp messages.
    """
    try:
        body = await request.json()
    except Exception:
        logger.error("Failed to parse webhook JSON")
        return JSONResponse({"status": "error"}, status_code=400)

    logger.info("📩 Webhook received")

    parsed = parse_webhook(body)
    if parsed is None:
        return JSONResponse({"status": "ok"})

    phone, message_text, message_id = parsed
    logger.info("📱 Message from %s: %s", phone, message_text[:100])

    try:
        await mark_as_read(message_id)
        response_text = await handle_message(phone, message_text)
        sent = await send_text_message(phone, response_text)
        if not sent:
            logger.error("Failed to send response to %s", phone)
    except Exception as e:
        logger.error("Error processing message from %s: %s", phone, str(e), exc_info=True)
        await send_text_message(
            phone,
            "⚠️ Something went wrong on our end. Please try again by typing *restart*."
        )

    return JSONResponse({"status": "ok"})


# ──────────────────────────────────────────────
# Local Testing Endpoint
# ──────────────────────────────────────────────

@app.post("/test")
async def test_message(request: Request):
    """Local testing endpoint"""
    try:
        body = await request.json()
        phone = body.get("phone", "test_user_001")
        message = body.get("message", "")

        if not message:
            return JSONResponse({"error": "message is required"}, status_code=400)

        response_text = await handle_message(phone, message)

        return JSONResponse({
            "phone": phone,
            "user_message": message,
            "bot_response": response_text,
        })

    except Exception as e:
        logger.error("Test endpoint error: %s", str(e), exc_info=True)
        return JSONResponse({"error": str(e)}, status_code=500)


# ──────────────────────────────────────────────
# Health Check
# ──────────────────────────────────────────────

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    return {
        "status": "healthy",
        "service": "Government Schemes AI Agent",
        "version": "1.0.0",
        "environment": settings.APP_ENV,
    }


from fastapi.responses import FileResponse

@app.get("/")
async def root():
    """Root endpoint — serve UI."""
    return FileResponse("app/static/index.html")
