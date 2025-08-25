import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { TranslationJob } from '../types'
import { uploadEpub, uploadPdf, getJobStatus } from '../api'

export const useTranslationStore = defineStore('translation', () => {
  const jobs = ref<TranslationJob[]>([])
  const currentJobId = ref<string | null>(null)
  const polling = ref(false)
  
  const currentJob = computed(() => {
    if (!currentJobId.value) return null
    return jobs.value.find(job => job.id === currentJobId.value) || null
  })
  
  async function createJob(file: File, targetLang: string): Promise<string> {
    const fileType = file.name.toLowerCase().endsWith('.epub') ? 'epub' : 'pdf'
    
    let jobResponse
    if (fileType === 'epub') {
      jobResponse = await uploadEpub(file, targetLang)
    } else {
      jobResponse = await uploadPdf(file, targetLang)
    }
    
    const job: TranslationJob = {
      id: jobResponse.jobId,
      fileName: file.name,
      fileType,
      targetLang,
      status: 'running',
      progress: 0,
      stats: { translatedChunks: 0, retries: 0, errors: 0 },
      createdAt: Date.now()
    }
    
    jobs.value.push(job)
    currentJobId.value = jobResponse.jobId
    
    startPolling()
    
    return jobResponse.jobId
  }
  
  async function updateJobStatus(jobId: string) {
    const status = await getJobStatus(jobId)
    const jobIndex = jobs.value.findIndex(job => job.id === jobId)
    
    if (jobIndex !== -1) {
      const job = jobs.value[jobIndex]
      jobs.value[jobIndex] = {
        ...job,
        status: status.status,
        progress: status.progress,
        current: status.current,
        stats: status.stats,
        lastError: status.lastError,
        downloadUrl: status.downloadUrl
      }
    }
    
    return status
  }
  
  function startPolling() {
    if (polling.value) return
    
    polling.value = true
    
    const poll = async () => {
      if (!currentJobId.value) {
        polling.value = false
        return
      }
      
      try {
        const status = await updateJobStatus(currentJobId.value)
        
        if (status.status === 'done' || status.status === 'error') {
          polling.value = false
          return
        }
        
        setTimeout(poll, 2000) // Poll every 2 seconds
      } catch (error) {
        console.error('Polling error:', error)
        setTimeout(poll, 5000) // Retry after 5 seconds on error
      }
    }
    
    poll()
  }
  
  function stopPolling() {
    polling.value = false
  }
  
  function clearJobs() {
    jobs.value = []
    currentJobId.value = null
    polling.value = false
  }
  
  return {
    jobs: computed(() => jobs.value),
    currentJob,
    currentJobId: computed(() => currentJobId.value),
    polling: computed(() => polling.value),
    createJob,
    updateJobStatus,
    startPolling,
    stopPolling,
    clearJobs
  }
})