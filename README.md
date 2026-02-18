# AIL PDF System

AI-powered PDF document analysis system. Upload a PDF, ask questions, and get highlighted answers with reasoning.

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
- `ANTHROPIC_API_KEY` - Claude API key (required)
- `GEMINI_API_KEY` - Google Gemini key for PDF OCR (recommended)
- `LOG_LEVEL` - Logging level (default: DEBUG)

### Frontend (`frontend/.env.local`)
- `NEXT_PUBLIC_BACKEND_URL` - Backend URL (default: http://localhost:8020)
