from pydantic import BaseModel
from typing import Optional, Dict, Any
from enum import Enum


class JobStatus(str, Enum):
    RUNNING = "running"
    DONE = "done" 
    ERROR = "error"
    CANCELED = "canceled"


class FileType(str, Enum):
    EPUB = "epub"
    PDF = "pdf"


class CurrentProgress(BaseModel):
    type: FileType
    chapter: Optional[str] = None
    page: Optional[int] = None


class JobStats(BaseModel):
    translatedChunks: int = 0
    retries: int = 0
    errors: int = 0


class LastError(BaseModel):
    type: str  # "OpenAI", "Parsing", "IO"
    msg: str


class JobResponse(BaseModel):
    jobId: str


class JobStatusResponse(BaseModel):
    status: JobStatus
    progress: int  # 0-100
    current: Optional[CurrentProgress] = None
    stats: JobStats
    lastError: Optional[LastError] = None
    downloadUrl: Optional[str] = None


class TranslationJob(BaseModel):
    id: str
    file_type: FileType
    target_lang: str
    status: JobStatus
    progress: int
    current: Optional[CurrentProgress] = None
    stats: JobStats
    last_error: Optional[LastError] = None
    input_path: str
    output_path: Optional[str] = None
    created_at: float
    updated_at: float