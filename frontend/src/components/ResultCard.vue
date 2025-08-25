<template>
  <div class="result-card" v-if="job && job.status !== 'running'">
    <div class="result-header">
      <h3>Translation Complete</h3>
      <span 
        class="status-badge" 
        :class="statusClass"
      >
        {{ statusText }}
      </span>
    </div>
    
    <div class="file-info">
      <div class="file-details">
        <div class="file-icon">
          {{ job.fileType === 'epub' ? '📖' : '📄' }}
        </div>
        <div class="file-meta">
          <h4>{{ job.fileName }}</h4>
          <p class="file-type">{{ job.fileType.toUpperCase() }} → {{ job.targetLang.toUpperCase() }}</p>
          <p class="completion-time">
            Completed {{ formatTime(job.createdAt) }}
          </p>
        </div>
      </div>
    </div>
    
    <div v-if="job.status === 'done'" class="download-section">
      <button 
        @click="handleDownload"
        :disabled="downloading"
        class="download-btn primary"
      >
        <span v-if="downloading">⏳ Downloading...</span>
        <span v-else>📥 Download Translated File</span>
      </button>
      
      <div class="download-info">
        <p class="download-hint">
          Your translated {{ job.fileType.toUpperCase() }} file is ready for download
        </p>
      </div>
    </div>
    
    <div v-else-if="job.status === 'error'" class="error-section">
      <div class="error-details">
        <h4>❌ Translation Failed</h4>
        <p v-if="job.lastError">
          <strong>{{ job.lastError.type }} Error:</strong> {{ job.lastError.msg }}
        </p>
        <p v-else>An unexpected error occurred during translation.</p>
      </div>
      
      <div class="error-actions">
        <button @click="$emit('retry')" class="retry-btn">
          🔄 Retry Translation
        </button>
        <button @click="$emit('newFile')" class="new-file-btn">
          📄 Try Another File
        </button>
      </div>
    </div>
    
    <div class="final-stats" v-if="job.stats">
      <h4>Translation Summary</h4>
      <div class="stats-grid">
        <div class="stat-item">
          <span class="stat-value">{{ job.stats.translatedChunks }}</span>
          <span class="stat-label">Chunks Translated</span>
        </div>
        <div class="stat-item" v-if="job.stats.retries > 0">
          <span class="stat-value">{{ job.stats.retries }}</span>
          <span class="stat-label">Retries</span>
        </div>
        <div class="stat-item" v-if="job.stats.errors > 0">
          <span class="stat-value error">{{ job.stats.errors }}</span>
          <span class="stat-label">Errors</span>
        </div>
        <div class="stat-item">
          <span class="stat-value">{{ formatDuration(job.createdAt) }}</span>
          <span class="stat-label">Duration</span>
        </div>
      </div>
    </div>
    
    <div class="actions">
      <button @click="$emit('newTranslation')" class="action-btn secondary">
        ➕ New Translation
      </button>
      <button @click="$emit('showHistory')" class="action-btn secondary">
        📋 View History
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { TranslationJob } from '../types'
import { downloadFile } from '../api'

interface Props {
  job?: TranslationJob
}

const props = defineProps<Props>()

const emit = defineEmits<{
  retry: []
  newFile: []
  newTranslation: []
  showHistory: []
}>()

const downloading = ref(false)

const statusClass = computed(() => ({
  'status-done': props.job?.status === 'done',
  'status-error': props.job?.status === 'error',
  'status-canceled': props.job?.status === 'canceled'
}))

const statusText = computed(() => {
  switch (props.job?.status) {
    case 'done':
      return 'Success'
    case 'error':
      return 'Failed'
    case 'canceled':
      return 'Canceled'
    default:
      return 'Unknown'
  }
})

async function handleDownload() {
  if (!props.job || !props.job.downloadUrl) return
  
  downloading.value = true
  
  try {
    const blob = await downloadFile(props.job.id)
    
    // Create download link
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    
    // Generate filename
    const originalName = props.job.fileName
    const extension = props.job.fileType
    const translatedName = originalName.replace(
      `.${extension}`, 
      `_translated.${extension}`
    )
    
    a.download = translatedName
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    window.URL.revokeObjectURL(url)
  } catch (error) {
    console.error('Download failed:', error)
    alert('Download failed. Please try again.')
  } finally {
    downloading.value = false
  }
}

function formatTime(timestamp: number): string {
  return new Date(timestamp).toLocaleString()
}

function formatDuration(startTime: number): string {
  const duration = Date.now() - startTime
  const seconds = Math.floor(duration / 1000)
  const minutes = Math.floor(seconds / 60)
  const hours = Math.floor(minutes / 60)
  
  if (hours > 0) {
    return `${hours}h ${minutes % 60}m`
  } else if (minutes > 0) {
    return `${minutes}m ${seconds % 60}s`
  } else {
    return `${seconds}s`
  }
}
</script>

<style scoped>
.result-card {
  width: 100%;
  max-width: 600px;
  margin: 24px auto;
  padding: 24px;
  border: 1px solid #e0e0e0;
  border-radius: 12px;
  background: white;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.result-header h3 {
  margin: 0;
  font-size: 24px;
  color: #333;
}

.status-badge {
  padding: 8px 16px;
  border-radius: 20px;
  font-weight: 600;
  font-size: 14px;
}

.status-done {
  background: #e8f5e8;
  color: #2e7d32;
}

.status-error {
  background: #ffebee;
  color: #c62828;
}

.status-canceled {
  background: #f5f5f5;
  color: #616161;
}

.file-info {
  margin-bottom: 24px;
}

.file-details {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px;
  background: #f8f9fa;
  border-radius: 8px;
}

.file-icon {
  font-size: 32px;
}

.file-meta h4 {
  margin: 0 0 8px 0;
  font-size: 18px;
  color: #333;
}

.file-type {
  margin: 0 0 4px 0;
  font-size: 14px;
  color: #666;
  font-weight: 600;
}

.completion-time {
  margin: 0;
  font-size: 14px;
  color: #888;
}

.download-section {
  margin-bottom: 24px;
  text-align: center;
}

.download-btn {
  padding: 16px 32px;
  font-size: 18px;
  font-weight: 600;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.3s ease;
  margin-bottom: 12px;
}

.download-btn.primary {
  background: #007bff;
  color: white;
}

.download-btn.primary:hover:not(:disabled) {
  background: #0056b3;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 123, 255, 0.3);
}

.download-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.download-info {
  color: #666;
  font-size: 14px;
}

.error-section {
  margin-bottom: 24px;
}

.error-details {
  padding: 16px;
  background: #fff5f5;
  border: 1px solid #fed7d7;
  border-radius: 8px;
  margin-bottom: 16px;
}

.error-details h4 {
  margin: 0 0 12px 0;
  color: #c62828;
}

.error-details p {
  margin: 0;
  color: #721c24;
}

.error-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
}

.retry-btn,
.new-file-btn {
  padding: 12px 20px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 600;
}

.retry-btn {
  background: #ffc107;
  color: #212529;
}

.new-file-btn {
  background: #6c757d;
  color: white;
}

.final-stats {
  margin-bottom: 24px;
}

.final-stats h4 {
  margin: 0 0 16px 0;
  color: #333;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 16px;
}

.stat-item {
  text-align: center;
  padding: 12px;
  background: #f8f9fa;
  border-radius: 8px;
}

.stat-value {
  display: block;
  font-size: 24px;
  font-weight: bold;
  color: #333;
}

.stat-value.error {
  color: #dc3545;
}

.stat-label {
  display: block;
  font-size: 12px;
  color: #666;
  margin-top: 4px;
}

.actions {
  display: flex;
  gap: 12px;
  justify-content: center;
  border-top: 1px solid #e9ecef;
  padding-top: 24px;
}

.action-btn {
  padding: 12px 20px;
  border: 2px solid #dee2e6;
  border-radius: 6px;
  background: white;
  color: #495057;
  cursor: pointer;
  font-weight: 600;
  transition: all 0.3s ease;
}

.action-btn.secondary:hover {
  background: #f8f9fa;
  border-color: #adb5bd;
}
</style>