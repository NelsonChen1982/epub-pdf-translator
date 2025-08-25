export interface JobResponse {
  jobId: string
}

export interface CurrentProgress {
  type: 'epub' | 'pdf'
  chapter?: string
  page?: number
}

export interface JobStats {
  translatedChunks: number
  retries: number
  errors: number
}

export interface LastError {
  type: string
  msg: string
}

export interface JobStatusResponse {
  status: 'running' | 'done' | 'error' | 'canceled'
  progress: number
  current?: CurrentProgress
  stats: JobStats
  lastError?: LastError
  downloadUrl?: string
}

export interface TranslationJob {
  id: string
  fileName: string
  fileType: 'epub' | 'pdf'
  targetLang: string
  status: 'running' | 'done' | 'error' | 'canceled'
  progress: number
  current?: CurrentProgress
  stats: JobStats
  lastError?: LastError
  downloadUrl?: string
  createdAt: number
}