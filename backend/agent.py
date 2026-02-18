"""
PDF Agent Module

Uses the Claude Agent SDK with built-in tools for PDF analysis.
https://platform.claude.com/docs/en/agent-sdk/overview
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

# Import Claude Agent SDK
try:
    from claude_agent_sdk import query, ClaudeAgentOptions
    AGENT_SDK_AVAILABLE = True
    log.info("claude-agent-sdk imported successfully")
except ImportError as e:
    AGENT_SDK_AVAILABLE = False
    query = None
    ClaudeAgentOptions = None
    log.error(f"claude-agent-sdk import failed: {e}")

# Log bundled CLI status at startup
def _check_bundled_cli():
    try:
        import claude_agent_sdk
        sdk_dir = Path(claude_agent_sdk.__file__).parent
        cli_name = "claude.exe" if platform.system() == "Windows" else "claude"
        bundled_path = sdk_dir / "_bundled" / cli_name
        log.info(f"SDK version: {getattr(claude_agent_sdk, '__version__', 'unknown')}")
        log.info(f"SDK location: {sdk_dir}")
        log.info(f"Bundled CLI path: {bundled_path}")
        log.info(f"Bundled CLI exists: {bundled_path.exists()}")
        if bundled_path.exists():
            log.info(f"Bundled CLI size: {bundled_path.stat().st_size} bytes")
    except Exception as e:
        log.warning(f"Could not check bundled CLI: {e}")

if AGENT_SDK_AVAILABLE:
    _check_bundled_cli()


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
# PDF STREAMING HANDLER
# ============================================================================

async def stream_pdf_response(
    message: str,
    session_id: Optional[str] = None
) -> AsyncGenerator[dict, None]:
    """
    Stream responses from Claude Agent SDK for PDF analysis.
    Includes thinking/reasoning events for transparency.
    """
    if not AGENT_SDK_AVAILABLE:
        log.error("stream_pdf_response called but claude-agent-sdk is not available")
        yield {"type": "error", "error": "claude-agent-sdk not installed. Run: pip install claude-agent-sdk"}
        return

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        log.error("ANTHROPIC_API_KEY not set in environment")
        yield {"type": "error", "error": "ANTHROPIC_API_KEY not configured"}
        return

    try:
        model = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
        pdf_skill = _skills.get("pdf_analysis")
        full_pdf_prompt = PDF_SYSTEM_PROMPT + ("\n\n" + pdf_skill if pdf_skill else "")

        log.info(f"[pdf-agent] Starting query — model={model}, session_id={session_id}, message={message[:80]}...")

        options = ClaudeAgentOptions(
            model=model,
            allowed_tools=["WebSearch", "WebFetch", "Read", "Glob", "Grep"],
            system_prompt=full_pdf_prompt,
            permission_mode="bypassPermissions",
        )

        if session_id:
            options.resume = session_id
            log.info(f"[pdf-agent] Resuming session: {session_id}")

        full_content = ""
        new_session_id = None

        loop = asyncio.get_running_loop()
        log.info(f"[pdf-agent] Event loop type: {type(loop).__name__}")
        log.info("[pdf-agent] Calling query() — spawning Claude Code subprocess...")

        async for message_event in query(prompt=message, options=options):
            event_type = getattr(message_event, 'type', None)
            subtype = getattr(message_event, 'subtype', None)
            log.debug(f"[pdf-agent] Event: type={event_type}, subtype={subtype}")

            if event_type == "system" and subtype == "init":
                new_session_id = getattr(message_event, 'session_id', None)
                log.info(f"[pdf-agent] Session initialized: {new_session_id}")
                continue

            # Handle thinking/reasoning events
            if event_type == "assistant" and subtype == "thinking":
                thinking_content = getattr(message_event, 'content', '')
                if thinking_content:
                    yield {"type": "thinking", "content": thinking_content}

            # Handle assistant text messages
            elif event_type == "assistant" and subtype == "text":
                content = getattr(message_event, 'content', '')
                if content:
                    full_content += content
                    yield {"type": "text", "content": content}

            # Handle tool use events
            elif event_type == "tool_use":
                tool_name = getattr(message_event, 'tool_name', getattr(message_event, 'name', 'Unknown'))
                tool_input = getattr(message_event, 'tool_input', getattr(message_event, 'input', ''))
                log.info(f"[pdf-agent] Tool call: {tool_name}")
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
                log.error(f"[pdf-agent] Error event from SDK: {error_msg}")
                yield {"type": "error", "error": str(error_msg)}
                return

        log.info(f"[pdf-agent] Stream complete — response length={len(full_content)}, session_id={new_session_id}")
        yield {"type": "complete", "content": full_content, "session_id": new_session_id}

    except Exception as e:
        log.error(f"[pdf-agent] Exception in stream_pdf_response: {type(e).__name__}: {e}")
        log.error(f"[pdf-agent] Traceback:\n{traceback.format_exc()}")
        yield {"type": "error", "error": f"{type(e).__name__}: {e}"}
