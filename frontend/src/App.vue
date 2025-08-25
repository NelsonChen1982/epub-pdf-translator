<template>
  <div id="app">
    <header class="app-header">
      <div class="container">
        <h1>📚 Translation Suite</h1>
        <p class="subtitle">EPUB ↔ EPUB • PDF ↔ PDF</p>
      </div>
    </header>

    <main class="app-main">
      <div class="container">
        <div v-if="!currentJob" class="upload-section">
          <FilePicker 
            @file-selected="handleFileSelected"
            @file-removed="handleFileRemoved"
          />
          
          <LanguageSelect 
            v-model="selectedLanguage"
            v-if="selectedFile"
          />
          
          <div v-if="selectedFile && selectedLanguage" class="start-section">
            <button 
              @click="startTranslation"
              :disabled="isStarting"
              class="start-btn"
            >
              <span v-if="isStarting">⏳ Starting...</span>
              <span v-else>🚀 Start Translation</span>
            </button>
          </div>
        </div>

        <div v-else class="translation-section">
          <ProgressBar 
            :progress="currentJob.progress"
            :status="currentJob.status"
            :current="currentJob.current"
            :stats="currentJob.stats"
          />
          
          <LogConsole 
            :job-id="currentJobId || undefined"
            :is-active="currentJob.status === 'running'"
            :last-error="currentJob.lastError"
            :stats="currentJob.stats"
          />
          
          <ResultCard 
            v-if="currentJob.status !== 'running'"
            :job="currentJob"
            @retry="handleRetry"
            @new-file="handleNewFile"
            @new-translation="handleNewTranslation"
            @show-history="handleShowHistory"
          />
        </div>

        <div v-if="jobs.length > 1" class="history-section">
          <h3>Recent Translations</h3>
          <div class="job-list">
            <div 
              v-for="job in recentJobs" 
              :key="job.id"
              :class="['job-item', { active: job.id === currentJobId }]"
              @click="selectJob(job.id)"
            >
              <div class="job-info">
                <span class="job-file">{{ job.fileName }}</span>
                <span class="job-lang">{{ job.fileType }} → {{ job.targetLang }}</span>
              </div>
              <span :class="['job-status', `status-${job.status}`]">
                {{ getStatusIcon(job.status) }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </main>

    <footer class="app-footer">
      <div class="container">
        <p>&copy; 2024 Translation Suite • Powered by OpenAI</p>
      </div>
    </footer>

    <!-- Error Toast -->
    <div v-if="errorMessage" class="error-toast" @click="errorMessage = ''">
      <span>❌ {{ errorMessage }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onUnmounted } from 'vue'
import { useTranslationStore } from './stores/translation'
import FilePicker from './components/FilePicker.vue'
import LanguageSelect from './components/LanguageSelect.vue'
import ProgressBar from './components/ProgressBar.vue'
import LogConsole from './components/LogConsole.vue'
import ResultCard from './components/ResultCard.vue'

const store = useTranslationStore()

const selectedFile = ref<File | null>(null)
const selectedLanguage = ref('zh-TW')
const isStarting = ref(false)
const errorMessage = ref('')

const currentJob = computed(() => store.currentJob)
const currentJobId = computed(() => store.currentJobId)
const jobs = computed(() => store.jobs)

const recentJobs = computed(() => {
  return jobs.value
    .filter(job => job.id !== currentJobId.value)
    .sort((a, b) => b.createdAt - a.createdAt)
    .slice(0, 5)
})

function handleFileSelected(file: File) {
  selectedFile.value = file
}

function handleFileRemoved() {
  selectedFile.value = null
}

async function startTranslation() {
  if (!selectedFile.value || !selectedLanguage.value) return
  
  isStarting.value = true
  errorMessage.value = ''
  
  try {
    await store.createJob(selectedFile.value, selectedLanguage.value)
  } catch (error) {
    console.error('Translation start failed:', error)
    errorMessage.value = 'Failed to start translation. Please try again.'
  } finally {
    isStarting.value = false
  }
}

function handleRetry() {
  if (!currentJob.value) return
  
  // Reset current job and retry with same file
  selectedFile.value = new File([], currentJob.value.fileName)
  selectedLanguage.value = currentJob.value.targetLang
  store.stopPolling()
  
  // In a real implementation, you might want to store the original file
  errorMessage.value = 'Please select the file again to retry translation'
}

function handleNewFile() {
  selectedFile.value = null
  selectedLanguage.value = 'zh-TW'
  store.stopPolling()
}

function handleNewTranslation() {
  selectedFile.value = null
  selectedLanguage.value = 'zh-TW'
  store.stopPolling()
}

function handleShowHistory() {
  // This could open a modal or navigate to a history page
  console.log('Show history:', jobs.value)
}

function selectJob(jobId: string) {
  // Switch to viewing a different job
  // This would require updating the store to support multiple active jobs
  console.log('Select job:', jobId)
}

function getStatusIcon(status: string): string {
  switch (status) {
    case 'running':
      return '⏳'
    case 'done':
      return '✅'
    case 'error':
      return '❌'
    case 'canceled':
      return '⚠️'
    default:
      return '❓'
  }
}

// Cleanup on unmount
onUnmounted(() => {
  store.stopPolling()
})

// Auto-hide error message
setTimeout(() => {
  if (errorMessage.value) {
    errorMessage.value = ''
  }
}, 5000)
</script>

<style scoped>
#app {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

.container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 20px;
}

.app-header {
  background: rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid rgba(255, 255, 255, 0.2);
  padding: 20px 0;
}

.app-header h1 {
  margin: 0 0 8px 0;
  color: white;
  font-size: 32px;
  font-weight: 700;
  text-align: center;
}

.subtitle {
  margin: 0;
  color: rgba(255, 255, 255, 0.9);
  font-size: 16px;
  text-align: center;
  font-weight: 500;
}

.app-main {
  flex: 1;
  padding: 40px 0;
}

.upload-section {
  background: white;
  border-radius: 16px;
  padding: 40px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
  backdrop-filter: blur(10px);
  margin-bottom: 20px;
}

.start-section {
  text-align: center;
  margin-top: 32px;
}

.start-btn {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  padding: 16px 48px;
  font-size: 18px;
  font-weight: 600;
  border-radius: 50px;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
}

.start-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 8px 25px rgba(102, 126, 234, 0.6);
}

.start-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  transform: none;
}

.translation-section {
  background: white;
  border-radius: 16px;
  padding: 20px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
  backdrop-filter: blur(10px);
}

.history-section {
  background: rgba(255, 255, 255, 0.9);
  border-radius: 16px;
  padding: 24px;
  margin-top: 20px;
  backdrop-filter: blur(10px);
}

.history-section h3 {
  margin: 0 0 16px 0;
  color: #333;
  font-size: 20px;
}

.job-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.job-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: white;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.job-item:hover {
  background: #f8f9fa;
  border-color: #007bff;
}

.job-item.active {
  background: #e3f2fd;
  border-color: #2196f3;
}

.job-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.job-file {
  font-weight: 600;
  color: #333;
}

.job-lang {
  font-size: 12px;
  color: #666;
}

.job-status {
  font-size: 20px;
}

.status-running {
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.app-footer {
  background: rgba(0, 0, 0, 0.2);
  color: rgba(255, 255, 255, 0.8);
  text-align: center;
  padding: 20px 0;
  margin-top: auto;
}

.app-footer p {
  margin: 0;
  font-size: 14px;
}

.error-toast {
  position: fixed;
  top: 20px;
  right: 20px;
  background: #dc3545;
  color: white;
  padding: 16px 24px;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(220, 53, 69, 0.3);
  cursor: pointer;
  animation: slideIn 0.3s ease;
  z-index: 1000;
}

@keyframes slideIn {
  from {
    transform: translateX(100%);
    opacity: 0;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
}

/* Responsive Design */
@media (max-width: 768px) {
  .container {
    padding: 0 16px;
  }
  
  .app-header h1 {
    font-size: 24px;
  }
  
  .upload-section {
    padding: 24px;
    margin: 0 8px 20px;
  }
  
  .translation-section {
    margin: 0 8px;
    padding: 16px;
  }
  
  .start-btn {
    padding: 12px 32px;
    font-size: 16px;
  }
}
</style>