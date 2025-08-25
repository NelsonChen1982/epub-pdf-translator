# Translation Suite (EPUB→EPUB, PDF→PDF)

A monorepo translation tool that preserves document structure while translating content using OpenAI.

## Features

- **EPUB→EPUB**: Maintains original structure, manifest, spine, and TOC
- **PDF→PDF**: Clean text-based output with proper paragraph formatting
- **Structure Preservation**: Chapter order and navigation links remain intact
- **OpenAI Integration**: Efficient translation with rate limiting and retry logic

## Project Structure

```
/translation-suite/
  backend/                # Python (FastAPI)
    app.py
    services/
      epub_processor.py   # EPUB parsing/translation/reconstruction
      pdf_processor.py    # PDF parsing/translation/rebuilding
      translator.py       # OpenAI API wrapper
      validators.py       # EPUB validation
      utils.py            # Utilities
    models/schemas.py     # Pydantic models
    .env.example
    requirements.txt
  frontend/               # Vue 3 (Vite)
    src/
      main.ts
      App.vue
      components/
        FilePicker.vue
        LanguageSelect.vue
        ProgressBar.vue
        LogConsole.vue
        ResultCard.vue
    .env.example
    package.json
```

## Setup

### Backend
```bash
cd backend
cp .env.example .env
# Edit .env with your OPENAI_API_KEY
pip install -r requirements.txt
uvicorn app:app --reload
```

### Frontend
```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

## API Endpoints

- `POST /jobs/epub` - Upload EPUB for translation
- `POST /jobs/pdf` - Upload PDF for translation
- `GET /jobs/{jobId}/status` - Check translation progress
- `GET /jobs/{jobId}/download` - Download translated file