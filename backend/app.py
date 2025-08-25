import os
import asyncio
import time
import logging
from typing import Dict, List, Optional
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import aiofiles
import threading

from models.schemas import (
    JobResponse, JobStatusResponse, JobStatus, FileType, 
    CurrentProgress, JobStats, LastError, TranslationJob
)
from services.epub_processor_v2 import EPUBProcessor
from services.pdf_processor import PDFProcessor
from services.utils import (
    create_temp_dir, cleanup_old_files, get_file_size, 
    is_allowed_file_type, generate_job_id
)

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="Translation Suite API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize processors
epub_processor = EPUBProcessor()
pdf_processor = PDFProcessor()

# In-memory job storage (in production, use Redis or database)
jobs: Dict[str, TranslationJob] = {}
jobs_lock = threading.Lock()

# In-memory log storage for each job
job_logs: Dict[str, List[str]] = {}
logs_lock = threading.Lock()

# Configuration
MAX_FILE_SIZE = int(os.getenv("UPLOAD_MAX_SIZE", 104857600))  # 100MB
ALLOWED_EPUB_EXTENSIONS = ['.epub']
ALLOWED_PDF_EXTENSIONS = ['.pdf']
TEMP_DIR = os.getenv("TEMP_DIR", "./temp")
TTL_HOURS = int(os.getenv("CLEANUP_TTL_HOURS", 24))


def create_job(file_type: FileType, target_lang: str, input_path: str) -> str:
    """Create a new translation job."""
    job_id = generate_job_id()
    
    job = TranslationJob(
        id=job_id,
        file_type=file_type,
        target_lang=target_lang,
        status=JobStatus.RUNNING,
        progress=0,
        stats=JobStats(),
        input_path=input_path,
        created_at=time.time(),
        updated_at=time.time()
    )
    
    with jobs_lock:
        jobs[job_id] = job
        
    # Initialize logs for this job
    with logs_lock:
        job_logs[job_id] = []
    
    return job_id


def update_job(job_id: str, **kwargs):
    """Update job status and stats."""
    with jobs_lock:
        if job_id in jobs:
            job = jobs[job_id]
            for key, value in kwargs.items():
                if hasattr(job, key):
                    setattr(job, key, value)
            job.updated_at = time.time()


def add_job_log(job_id: str, message: str):
    """Add a log message for a specific job."""
    timestamp = time.strftime('%H:%M:%S')
    log_entry = f"{timestamp} - {message}"
    
    with logs_lock:
        if job_id in job_logs:
            job_logs[job_id].append(log_entry)
            # Keep only last 100 log entries
            if len(job_logs[job_id]) > 100:
                job_logs[job_id] = job_logs[job_id][-100:]


def progress_callback(job_id: str, file_type: str, current_item: str, current: int, total: int):
    """Progress callback for translation jobs."""
    progress = int((current / total) * 100) if total > 0 else 0
    
    current_progress = CurrentProgress(
        type=FileType(file_type),
        chapter=current_item if file_type == "epub" else None,
        page=current if file_type == "pdf" else None
    )
    
    update_job(
        job_id,
        progress=progress,
        current=current_progress
    )


async def process_epub_job(job_id: str, input_path: str, target_lang: str):
    """Background task for EPUB processing."""
    try:
        add_job_log(job_id, "Starting EPUB processing...")
        output_path = input_path.replace('.epub', '_translated.epub')
        
        def callback(file_type, current_item, current, total):
            progress_callback(job_id, file_type, current_item, current, total)
            add_job_log(job_id, f"Processing {current_item}")
        
        result = await epub_processor.process_epub(
            input_path, output_path, target_lang, callback
        )
        
        if result["success"]:
            update_job(
                job_id,
                status=JobStatus.DONE,
                progress=100,
                output_path=output_path
            )
        else:
            error = LastError(type="Processing", msg=result.get("error", "Unknown error"))
            update_job(
                job_id,
                status=JobStatus.ERROR,
                last_error=error
            )
    
    except Exception as e:
        logger.error(f"EPUB job {job_id} failed: {e}")
        error = LastError(type="Processing", msg=str(e))
        update_job(
            job_id,
            status=JobStatus.ERROR,
            last_error=error
        )


async def process_pdf_job(job_id: str, input_path: str, target_lang: str):
    """Background task for PDF processing."""
    try:
        output_path = input_path.replace('.pdf', '_translated.pdf')
        
        def callback(file_type, current_item, current, total):
            progress_callback(job_id, file_type, current_item, current, total)
        
        result = await pdf_processor.process_pdf(
            input_path, output_path, target_lang, callback
        )
        
        if result["success"]:
            update_job(
                job_id,
                status=JobStatus.DONE,
                progress=100,
                output_path=output_path
            )
        else:
            error = LastError(type="Processing", msg=result.get("error", "Unknown error"))
            update_job(
                job_id,
                status=JobStatus.ERROR,
                last_error=error
            )
    
    except Exception as e:
        logger.error(f"PDF job {job_id} failed: {e}")
        error = LastError(type="Processing", msg=str(e))
        update_job(
            job_id,
            status=JobStatus.ERROR,
            last_error=error
        )


@app.post("/jobs/epub", response_model=JobResponse)
async def upload_epub(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    targetLang: str = Form(...)
):
    """Upload EPUB file for translation."""
    
    # Validate file
    if not file.filename or not is_allowed_file_type(file.filename, ALLOWED_EPUB_EXTENSIONS):
        raise HTTPException(status_code=400, detail="Invalid file type. Only .epub files allowed.")
    
    # Check file size
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail=f"File too large. Max size: {MAX_FILE_SIZE} bytes")
    
    # Save uploaded file
    temp_dir = create_temp_dir()
    input_path = os.path.join(temp_dir, file.filename)
    
    async with aiofiles.open(input_path, 'wb') as f:
        await f.write(content)
    
    # Create job
    job_id = create_job(FileType.EPUB, targetLang, input_path)
    
    # Start background processing
    background_tasks.add_task(process_epub_job, job_id, input_path, targetLang)
    
    return JobResponse(jobId=job_id)


@app.post("/jobs/pdf", response_model=JobResponse)
async def upload_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    targetLang: str = Form(...)
):
    """Upload PDF file for translation."""
    
    # Validate file
    if not file.filename or not is_allowed_file_type(file.filename, ALLOWED_PDF_EXTENSIONS):
        raise HTTPException(status_code=400, detail="Invalid file type. Only .pdf files allowed.")
    
    # Check file size
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail=f"File too large. Max size: {MAX_FILE_SIZE} bytes")
    
    # Save uploaded file
    temp_dir = create_temp_dir()
    input_path = os.path.join(temp_dir, file.filename)
    
    async with aiofiles.open(input_path, 'wb') as f:
        await f.write(content)
    
    # Create job
    job_id = create_job(FileType.PDF, targetLang, input_path)
    
    # Start background processing
    background_tasks.add_task(process_pdf_job, job_id, input_path, targetLang)
    
    return JobResponse(jobId=job_id)


@app.get("/jobs/{job_id}/status", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """Get translation job status."""
    
    with jobs_lock:
        if job_id not in jobs:
            raise HTTPException(status_code=404, detail="Job not found")
        
        job = jobs[job_id]
    
    download_url = None
    if job.status == JobStatus.DONE and job.output_path:
        download_url = f"/jobs/{job_id}/download"
    
    return JobStatusResponse(
        status=job.status,
        progress=job.progress,
        current=job.current,
        stats=job.stats,
        lastError=job.last_error,
        downloadUrl=download_url
    )


@app.get("/jobs/{job_id}/download")
async def download_result(job_id: str):
    """Download translated file."""
    
    with jobs_lock:
        if job_id not in jobs:
            raise HTTPException(status_code=404, detail="Job not found")
        
        job = jobs[job_id]
    
    if job.status != JobStatus.DONE or not job.output_path:
        raise HTTPException(status_code=400, detail="Translation not completed")
    
    if not os.path.exists(job.output_path):
        raise HTTPException(status_code=404, detail="Output file not found")
    
    # Determine filename and media type
    original_filename = os.path.basename(job.input_path)
    if job.file_type == FileType.EPUB:
        filename = original_filename.replace('.epub', '_translated.epub')
        media_type = 'application/epub+zip'
    else:
        filename = original_filename.replace('.pdf', '_translated.pdf')
        media_type = 'application/pdf'
    
    return FileResponse(
        job.output_path,
        media_type=media_type,
        filename=filename
    )


@app.on_event("startup")
async def startup_event():
    """Startup event handler."""
    # Create temp directory
    os.makedirs(TEMP_DIR, exist_ok=True)
    
    # Start cleanup task
    async def cleanup_task():
        while True:
            try:
                cleanup_old_files(TEMP_DIR, TTL_HOURS)
            except Exception as e:
                logger.error(f"Cleanup task failed: {e}")
            await asyncio.sleep(3600)  # Run every hour
    
    asyncio.create_task(cleanup_task())
    
    logger.info("Translation Suite API started")


@app.get("/jobs/{job_id}/logs")
async def get_job_logs(job_id: str):
    """Get logs for a specific job."""
    
    with logs_lock:
        if job_id not in job_logs:
            raise HTTPException(status_code=404, detail="Job logs not found")
        
        logs = job_logs[job_id].copy()
    
    return {"logs": logs}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": time.time()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)