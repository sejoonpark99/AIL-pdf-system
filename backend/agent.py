"""
PDF Agent Module

Uses the Anthropic Python SDK for direct API streaming (lightweight, works on all hosts).
Falls back to Claude Agent SDK locally if USE_AGENT_SDK=true is set.
"""

import os
import sys
import asyncio
import logging
import traceback
import platform
from pathlib import Path
from typing import AsyncGenerator, Optional
from dotenv import load_dotenv

# Ensure ProactorEventLoop on Windows (required for subprocess support)
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

load_dotenv()

log = logging.getLogger("pdf-agent")

# Import skills loader
from skills import load_skills_from_directory

# Load skills at startup
_skills = load_skills_from_directory()

# Check which backend to use
USE_AGENT_SDK = os.environ.get("USE_AGENT_SDK", "").lower() == "true"

# Import Anthropic SDK (lightweight, always available)
try:
    import anthropic
    ANTHROPIC_SDK_AVAILABLE = True
    log.info("anthropic SDK imported successfully")
except ImportError:
    ANTHROPIC_SDK_AVAILABLE = False
    log.warning("anthropic SDK not available")

# Import Claude Agent SDK (heavy, optional — for local dev)
AGENT_SDK_AVAILABLE = False
query = None
ClaudeAgentOptions = None

if USE_AGENT_SDK:
    try:
        from claude_agent_sdk import query, ClaudeAgentOptions
        AGENT_SDK_AVAILABLE = True
        log.info("claude-agent-sdk imported successfully (USE_AGENT_SDK=true)")
    except ImportError as e:
        log.warning(f"claude-agent-sdk not available, falling back to direct API: {e}")


# ============================================================================
# PDF SYSTEM PROMPT
# ============================================================================

PDF_SYSTEM_PROMPT = """You are an expert PDF document analyst. You read and analyze PDF documents thoroughly.

When answering questions about a PDF:
1. Reference specific page numbers when possible
2. Quote relevant text from the document using <<highlight page=N>>exact quoted text<</highlight>> markers, where N is the page number. Keep the quoted text SHORT — use only the most relevant phrase (5-15 words max), not full paragraphs. Quote the exact text as it appears in the document.
3. Provide comprehensive, well-structured answers
4. If information is not found in the document, say so clearly

Format your responses in markdown when appropriate.
"""


# ============================================================================
# CONVERSATION HISTORY (simple in-memory store for session continuity)
# ============================================================================

_conversations: dict[str, list[dict]] = {}


# ============================================================================
# DIRECT ANTHROPIC API STREAMING (lightweight — works everywhere)
# ============================================================================

async def _stream_anthropic_direct(
    message: str,
    session_id: Optional[str] = None
) -> AsyncGenerator[dict, None]:
    """Stream responses using the Anthropic Python SDK directly."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        yield {"type": "error", "error": "ANTHROPIC_API_KEY not configured"}
        return

    model = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
    pdf_skill = _skills.get("pdf_analysis")
    system_prompt = PDF_SYSTEM_PROMPT + ("\n\n" + pdf_skill if pdf_skill else "")

    # Build message history for session continuity
    if session_id and session_id in _conversations:
        messages = _conversations[session_id].copy()
        messages.append({"role": "user", "content": message})
    else:
        messages = [{"role": "user", "content": message}]

    log.info(f"[pdf-agent] Direct API call — model={model}, messages={len(messages)}")

    try:
        client = anthropic.AsyncAnthropic(api_key=api_key)
        full_content = ""

        async with client.messages.stream(
            model=model,
            max_tokens=8192,
            system=system_prompt,
            messages=messages,
        ) as stream:
            async for event in stream:
                if event.type == "content_block_delta":
                    if hasattr(event.delta, "text"):
                        text = event.delta.text
                        full_content += text
                        yield {"type": "text", "content": text}

        # Generate a session ID if we don't have one
        if not session_id:
            import uuid
            session_id = str(uuid.uuid4())

        # Store conversation history
        messages.append({"role": "assistant", "content": full_content})
        _conversations[session_id] = messages

        # Prune old conversations (keep max 50)
        if len(_conversations) > 50:
            oldest = list(_conversations.keys())[0]
            del _conversations[oldest]

        log.info(f"[pdf-agent] Direct API complete — length={len(full_content)}, session={session_id}")
        yield {"type": "complete", "content": full_content, "session_id": session_id}

    except Exception as e:
        log.error(f"[pdf-agent] Direct API error: {type(e).__name__}: {e}")
        yield {"type": "error", "error": str(e)}


# ============================================================================
# CLAUDE AGENT SDK STREAMING (heavy — for local dev only)
# ============================================================================

async def _stream_agent_sdk(
    message: str,
    session_id: Optional[str] = None
) -> AsyncGenerator[dict, None]:
    """Stream responses using the Claude Agent SDK (spawns subprocess)."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        yield {"type": "error", "error": "ANTHROPIC_API_KEY not configured"}
        return

    model = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
    pdf_skill = _skills.get("pdf_analysis")
    full_pdf_prompt = PDF_SYSTEM_PROMPT + ("\n\n" + pdf_skill if pdf_skill else "")

    log.info(f"[pdf-agent] Agent SDK query — model={model}, session_id={session_id}")

    try:
        options = ClaudeAgentOptions(
            model=model,
            allowed_tools=["WebSearch", "WebFetch", "Read", "Glob", "Grep"],
            system_prompt=full_pdf_prompt,
            permission_mode="bypassPermissions",
        )

        if session_id:
            options.resume = session_id

        full_content = ""
        new_session_id = None

        async for message_event in query(prompt=message, options=options):
            event_type = getattr(message_event, 'type', None)
            subtype = getattr(message_event, 'subtype', None)

            if event_type == "system" and subtype == "init":
                new_session_id = getattr(message_event, 'session_id', None)
                continue

            if event_type == "assistant" and subtype == "thinking":
                thinking_content = getattr(message_event, 'content', '')
                if thinking_content:
                    yield {"type": "thinking", "content": thinking_content}

            elif event_type == "assistant" and subtype == "text":
                content = getattr(message_event, 'content', '')
                if content:
                    full_content += content
                    yield {"type": "text", "content": content}

            elif event_type == "tool_use":
                tool_name = getattr(message_event, 'tool_name', getattr(message_event, 'name', 'Unknown'))
                tool_input = getattr(message_event, 'tool_input', getattr(message_event, 'input', ''))
                if isinstance(tool_input, dict):
                    import json
                    tool_input = json.dumps(tool_input)
                yield {
                    "type": "tool_call",
                    "tool_name": tool_name,
                    "tool_input": str(tool_input) if tool_input else ""
                }

            elif event_type == "tool_result":
                pass

            elif hasattr(message_event, 'result'):
                result = message_event.result
                if result and result != full_content:
                    full_content = result

            elif event_type == "error":
                error_msg = getattr(message_event, 'error', getattr(message_event, 'message', 'Unknown error'))
                yield {"type": "error", "error": str(error_msg)}
                return

        log.info(f"[pdf-agent] Agent SDK complete — length={len(full_content)}, session={new_session_id}")
        yield {"type": "complete", "content": full_content, "session_id": new_session_id}

    except Exception as e:
        log.error(f"[pdf-agent] Agent SDK error: {type(e).__name__}: {e}")
        log.error(f"[pdf-agent] Traceback:\n{traceback.format_exc()}")
        yield {"type": "error", "error": f"{type(e).__name__}: {e}"}


# ============================================================================
# PUBLIC ENTRY POINT — auto-selects backend
# ============================================================================

async def stream_pdf_response(
    message: str,
    session_id: Optional[str] = None
) -> AsyncGenerator[dict, None]:
    """
    Stream PDF analysis responses.
    Uses Agent SDK if USE_AGENT_SDK=true and available, otherwise direct Anthropic API.
    """
    if USE_AGENT_SDK and AGENT_SDK_AVAILABLE:
        log.info("[pdf-agent] Using Claude Agent SDK backend")
        async for event in _stream_agent_sdk(message, session_id):
            yield event
    elif ANTHROPIC_SDK_AVAILABLE:
        log.info("[pdf-agent] Using direct Anthropic API backend")
        async for event in _stream_anthropic_direct(message, session_id):
            yield event
    else:
        yield {"type": "error", "error": "No AI backend available. Install anthropic: pip install anthropic"}
