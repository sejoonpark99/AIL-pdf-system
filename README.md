# AIL PDF System

AI-powered PDF document analysis system. Upload a PDF, ask questions, and get highlighted answers with reasoning.

## How It Works

1. **Upload** a PDF through the browser
2. **Gemini 2.5 Flash** performs OCR on the PDF, extracting text page-by-page with full fidelity (names, dates, numbers preserved exactly)
3. The extracted text is sent alongside your question to **Claude Haiku 4.5** via the Claude Agent SDK
4. Claude analyzes the document and responds with highlighted evidence — quoted passages are mapped back onto the PDF viewer with red highlight overlays
5. Follow-up questions reuse the same Claude session, so the model retains full conversation context without re-uploading

## Tech Stack

### Frontend — Next.js 16 + React 19
- **react-pdf** renders the uploaded PDF in-browser with a text layer, enabling per-span highlight overlays
- **Framer Motion** powers the collapsible sidebar and menu animations
- **Sonner** for toast notifications
- **Tailwind CSS 4** + **shadcn/ui** component library (Radix primitives)
- SSE streaming displays Claude's reasoning and response in real-time as it generates

### Backend — FastAPI + Python
- **FastAPI** with SSE (Server-Sent Events) for streaming responses back to the frontend
- **Claude Agent SDK** spawns a Claude Code subprocess with tool access (WebSearch, Read, Glob, Grep) — this lets the model use tools during analysis if needed
- **Loguru** for structured terminal logging

### AI Models

| Model | Role | Why |
|-------|------|-----|
| **Gemini 2.5 Flash** | PDF OCR / text extraction | Natively accepts PDF as input (base64), handles scanned documents and complex layouts far better than library-based extraction (PyPDF2). Fast and cheap — processes a full PDF in seconds. Falls back to PyPDF2 if Gemini is unavailable. |
| **Claude Haiku 4.5** | Document Q&A and reasoning | Fast, low-latency responses for conversational PDF analysis. Supports extended thinking for transparent reasoning. Cost-effective for high-volume document queries while still producing high-quality structured answers with page citations. |

### Highlight System
Claude is instructed to wrap quoted evidence in `<<highlight page=N>>text<</highlight>>` markers. The frontend parses these markers, maps them to the PDF text layer using fuzzy normalized matching (handles OCR artifacts and whitespace differences), and renders red highlight overlays on the corresponding spans.

## Setup

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API keys
uvicorn api:app --port 8020
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000/pdf

## Environment Variables

### Backend (`backend/.env`)
- `ANTHROPIC_API_KEY` — Claude API key (required)
- `GEMINI_API_KEY` — Google Gemini key for PDF OCR (recommended, falls back to PyPDF2 without it)
- `LOG_LEVEL` — Logging level (default: DEBUG)

### Frontend (`frontend/.env.local`)
- `NEXT_PUBLIC_BACKEND_URL` — Backend URL (default: http://localhost:8020)
