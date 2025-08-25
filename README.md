# Translation Suite (EPUB→EPUB, PDF→PDF)

A monorepo translation tool that preserves document structure while translating content using OpenAI.

## ✨ Features

- **EPUB→EPUB**: Maintains original structure, manifest, spine, and TOC using professional `ebooklib`
- **PDF→PDF**: Clean text-based output with proper paragraph formatting
- **Structure Preservation**: Chapter order and navigation links remain intact
- **OpenAI Integration**: Efficient translation with rate limiting and retry logic
- **Real-time Progress**: Live progress tracking with detailed processing logs
- **Web Interface**: Modern Vue.js frontend with drag-drop file upload
- **Quality Assurance**: Automatic validation and error recovery

## Project Structure

```
/translation-suite/
  backend/                # Python (FastAPI)
    app.py
    services/
      epub_processor_v2.py # EPUB processing using ebooklib
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

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- Node.js 16+
- OpenAI API Key

### Backend Setup
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your OPENAI_API_KEY
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Setup
```bash
cd frontend
npm install
cp .env.example .env  # If needed
npm run dev
# Visit http://localhost:5173
```

## 📖 Usage

1. **Upload File**: Drag & drop or select your EPUB/PDF file
2. **Choose Language**: Select target translation language
3. **Start Translation**: Click "Start Translation" 
4. **Monitor Progress**: Watch real-time progress with detailed logs
5. **Download Result**: Download the translated file when complete

## 🔧 Environment Variables

Create `.env` in the `backend` directory:
```env
# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o-mini

# Translation Settings  
TRANS_MAX_RETRIES=3
TRANS_MAX_CONCURRENCY=3

# File Upload Settings
UPLOAD_MAX_SIZE=104857600  # 100MB
TEMP_DIR=./temp
CLEANUP_TTL_HOURS=24
```

## 📡 API Endpoints

- `POST /jobs/epub` - Upload EPUB for translation
- `POST /jobs/pdf` - Upload PDF for translation  
- `GET /jobs/{jobId}/status` - Check translation progress
- `GET /jobs/{jobId}/logs` - Get detailed processing logs
- `GET /jobs/{jobId}/download` - Download translated file

## 🛠️ Technical Stack

### Backend
- **FastAPI**: Modern Python web framework
- **ebooklib**: Professional EPUB processing
- **pdfminer.six**: PDF text extraction
- **BeautifulSoup**: Safe HTML parsing
- **OpenAI API**: Translation engine

### Frontend  
- **Vue 3**: Progressive JavaScript framework
- **TypeScript**: Type-safe development
- **Vite**: Fast build tool
- **Pinia**: State management

## 🤝 Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/amazing-feature`  
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open Pull Request

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

---
**Built with ❤️ using OpenAI, Vue.js, and FastAPI**