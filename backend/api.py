"""
PDF Analysis API - FastAPI Routes Layer

Minimal API with CORS, health check, and PDF question endpoint.
"""

import sys
import asyncio

# Windows requires ProactorEventLoop for subprocess support (used by claude-agent-sdk)
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional

# Import business logic from main.py
import main

# Import Loguru logger
from logger import get_logger

log = get_logger()

# FastAPI app
app = FastAPI(title="PDF Analysis API")

# CORS middleware - Allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/ping")
async def ping():
    """Simple health check endpoint."""
    return {"status": "ok", "service": "pdf-analysis-api"}


@app.post("/pdf/ask")
async def pdf_ask(
    request: Request,
    file: UploadFile = File(None),
    question: str = Form(...),
    session_id: Optional[str] = Form(None),
    sdk_session_id: Optional[str] = Form(None),
):
    """SSE endpoint for asking questions about a PDF."""
    file_content = None
    filename = None
    if file and file.filename:
        file_content = await file.read()
        filename = file.filename

    return StreamingResponse(
        main.pdf_ask_handler(
            file_content=file_content,
            filename=filename,
            question=question,
            session_id=session_id,
            sdk_session_id=sdk_session_id,
            request=request,
        ),
        media_type="text/event-stream"
    )


if __name__ == "__main__":
    import uvicorn
    import logging

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    uvicorn.run(app, host="0.0.0.0", port=8020, log_level="info", loop="asyncio")
