import axios from 'axios'
import { JobResponse, JobStatusResponse } from '../types'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

const api = axios.create({
  baseURL: API_BASE,
  timeout: 30000
})

export async function uploadEpub(file: File, targetLang: string): Promise<JobResponse> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('targetLang', targetLang)
  
  const response = await api.post('/jobs/epub', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  })
  
  return response.data
}

export async function uploadPdf(file: File, targetLang: string): Promise<JobResponse> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('targetLang', targetLang)
  
  const response = await api.post('/jobs/pdf', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  })
  
  return response.data
}

export async function getJobStatus(jobId: string): Promise<JobStatusResponse> {
  const response = await api.get(`/jobs/${jobId}/status`)
  return response.data
}

export function getDownloadUrl(jobId: string): string {
  return `${API_BASE}/jobs/${jobId}/download`
}

export async function downloadFile(jobId: string): Promise<Blob> {
  const response = await api.get(`/jobs/${jobId}/download`, {
    responseType: 'blob'
  })
  return response.data
}

export async function getJobLogs(jobId: string): Promise<{ logs: string[] }> {
  const response = await api.get(`/jobs/${jobId}/logs`)
  return response.data
}