"""
PDF Analysis Main - Core PDF Logic

This module contains the business logic for PDF text extraction and question handling.
Uses Gemini Flash for OCR with PyPDF2 fallback.
"""

import os
import json
import logging
from dotenv import load_dotenv
from typing import Optional

load_dotenv()

# Configure logging
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO))
console_logger = logging.getLogger("pdf-backend")

# Anthropic configuration
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

# Gemini configuration (for PDF OCR)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")


def pdf_ask_handler(
    file_content: Optional[bytes] = None,
    filename: Optional[str] = None,
    question: str = "",
    session_id: Optional[str] = None,
    sdk_session_id: Optional[str] = None,
    request=None
):
    """
    SSE endpoint for asking questions about a PDF.
    Extracts text from PDF and sends it with the question to Claude.
    """
    console_logger.info(f"PDF ask request: {question[:100]}...")

    async def event_generator():
        try:
            yield f"data: {json.dumps({'type': 'status', 'message': 'Processing PDF...'})}\n\n"

            if not ANTHROPIC_API_KEY:
                yield f"data: {json.dumps({'type': 'error', 'error': 'ANTHROPIC_API_KEY not configured'})}\n\n"
                return

            # Extract text from PDF if file provided
            pdf_text = ""
            if file_content and filename:
                ext = filename.lower().split('.')[-1] if '.' in filename else ''
                if ext == 'pdf':
                    # Try Gemini Flash OCR first (much better for scanned docs)
                    if GEMINI_API_KEY:
                        try:
                            import base64
                            from google import genai

                            yield f"data: {json.dumps({'type': 'status', 'message': 'Running OCR with Gemini Flash...'})}\n\n"

                            client = genai.Client(api_key=GEMINI_API_KEY)
                            pdf_b64 = base64.standard_b64encode(file_content).decode("utf-8")

                            response = client.models.generate_content(
                                model="gemini-2.5-flash",
                                contents=[
                                    {
                                        "parts": [
                                            {"inline_data": {"mime_type": "application/pdf", "data": pdf_b64}},
                                            {"text": "Extract ALL text from this PDF. For each page, output exactly:\n\n[Page N]\n<all text on that page>\n\nPreserve the original text exactly as written — names, dates, numbers, abbreviations. Do not summarize or paraphrase. Include every line of text you can read."}
                                        ]
                                    }
                                ],
                            )
                            pdf_text = response.text
                            console_logger.info(f"Gemini OCR extracted {len(pdf_text)} chars from PDF")
                        except Exception as e:
                            console_logger.warning(f"Gemini OCR failed, falling back to PyPDF2: {e}")
                            pdf_text = ""

                    # Fallback to PyPDF2 if Gemini not available or failed
                    if not pdf_text:
                        try:
                            from PyPDF2 import PdfReader
                            import io
                            reader = PdfReader(io.BytesIO(file_content))
                            pages = []
                            for i, page in enumerate(reader.pages):
                                page_text = page.extract_text()
                                if page_text:
                                    pages.append(f"[Page {i+1}]\n{page_text}")
                            pdf_text = "\n\n".join(pages)
                        except Exception as e:
                            yield f"data: {json.dumps({'type': 'error', 'error': f'Failed to extract PDF text: {str(e)}'})}\n\n"
                            return
                else:
                    try:
                        pdf_text = file_content.decode('utf-8')
                    except Exception:
                        yield f"data: {json.dumps({'type': 'error', 'error': 'Unsupported file format'})}\n\n"
                        return

            # Build the prompt with PDF context
            if pdf_text:
                prompt = f"""Here is the content of a PDF document:

<pdf_content>
{pdf_text}
</pdf_content>

Question: {question}

When referencing specific parts of the PDF, wrap the quoted text in <<highlight page=N>>exact quoted text<</highlight>> markers where N is the page number. Keep highlighted quotes SHORT (5-15 words), and quote the exact text as it appears in the document."""
            else:
                prompt = question

            yield f"data: {json.dumps({'type': 'status', 'message': 'Analyzing document...'})}\n\n"

            full_content = ""
            try:
                from agent import stream_pdf_response
                async for event in stream_pdf_response(prompt, sdk_session_id):
                    event_type = event.get("type")

                    if event_type == "thinking":
                        yield f"data: {json.dumps({'type': 'thinking', 'content': event.get('content', '')})}\n\n"

                    elif event_type == "text":
                        content = event.get("content", "")
                        full_content += content
                        yield f"data: {json.dumps({'type': 'text', 'content': content})}\n\n"

                    elif event_type == "tool_call":
                        yield f"data: {json.dumps({'type': 'tool_call', 'tool_name': event.get('tool_name'), 'tool_input': event.get('tool_input')})}\n\n"

                    elif event_type == "complete":
                        full_content = event.get("content", full_content)
                        returned_sdk_session_id = event.get("session_id")
                        yield f"data: {json.dumps({'type': 'complete', 'content': full_content, 'session_id': returned_sdk_session_id})}\n\n"

                    elif event_type == "error":
                        yield f"data: {json.dumps({'type': 'error', 'error': event.get('error')})}\n\n"

            except Exception as api_error:
                console_logger.error(f"Claude API error in PDF handler: {str(api_error)}")
                yield f"data: {json.dumps({'type': 'error', 'error': str(api_error)})}\n\n"

        except Exception as e:
            console_logger.error(f"Error in PDF ask handler: {str(e)}")
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

        finally:
            yield "data: [DONE]\n\n"

    return event_generator()
