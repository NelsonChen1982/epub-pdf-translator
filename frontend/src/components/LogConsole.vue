<template>
  <div class="log-console" v-if="logs.length > 0 || lastError">
    <div class="log-header">
      <h4>Process Log</h4>
      <button @click="clearLogs" class="clear-btn">Clear</button>
    </div>
    
    <div class="log-content" ref="logContainer">
      <div
        v-for="(log, index) in logs"
        :key="index"
        :class="['log-entry', `log-${log.level}`]"
      >
        <span class="log-timestamp">{{ formatTime(log.timestamp) }}</span>
        <span class="log-level">{{ log.level.toUpperCase() }}</span>
        <span class="log-message">{{ log.message }}</span>
      </div>
      
      <div v-if="lastError" class="log-entry log-error">
        <span class="log-timestamp">{{ formatTime(Date.now()) }}</span>
        <span class="log-level">ERROR</span>
        <span class="log-message">
          [{{ lastError.type }}] {{ lastError.msg }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, onMounted, onUnmounted } from 'vue'
import type { LastError } from '../types'
import { getJobLogs } from '../api'

interface LogEntry {
  timestamp: number
  level: 'info' | 'warning' | 'error'
  message: string
}

interface Props {
  jobId?: string
  lastError?: LastError
  isActive?: boolean
  stats?: {
    translatedChunks: number
    retries: number
    errors: number
  }
}

const props = defineProps<Props>()

const logs = ref<LogEntry[]>([])
const logContainer = ref<HTMLElement>()
const rawLogs = ref<string[]>([])
let logPollingInterval: number | null = null

function addLog(level: 'info' | 'warning' | 'error', message: string) {
  logs.value.push({
    timestamp: Date.now(),
    level,
    message
  })
  
  // Auto-scroll to bottom
  nextTick(() => {
    if (logContainer.value) {
      logContainer.value.scrollTop = logContainer.value.scrollHeight
    }
  })
}

function clearLogs() {
  logs.value = []
}

function formatTime(timestamp: number): string {
  return new Date(timestamp).toLocaleTimeString()
}

async function fetchLogs() {
  if (!props.jobId) return
  
  try {
    const response = await getJobLogs(props.jobId)
    const newLogs = response.logs
    
    // Only add new logs
    if (newLogs.length > rawLogs.value.length) {
      const newMessages = newLogs.slice(rawLogs.value.length)
      rawLogs.value = newLogs
      
      newMessages.forEach(message => {
        const level = message.includes('ERROR') ? 'error' : 
                     message.includes('WARNING') ? 'warning' : 'info'
        addLog(level, message)
      })
    }
  } catch (error) {
    console.error('Failed to fetch logs:', error)
  }
}

// Start polling for logs when job is active
watch(() => [props.jobId, props.isActive], ([jobId, isActive]) => {
  if (logPollingInterval) {
    clearInterval(logPollingInterval)
    logPollingInterval = null
  }
  
  if (jobId && isActive) {
    fetchLogs() // Initial fetch
    logPollingInterval = setInterval(fetchLogs, 2000) // Poll every 2 seconds
  }
}, { immediate: true })

// Watch for changes in stats to generate log entries (fallback)
watch(() => props.stats, (newStats, oldStats) => {
  if (!newStats || !oldStats) return
  
  if (newStats.translatedChunks > oldStats.translatedChunks) {
    const newChunks = newStats.translatedChunks - oldStats.translatedChunks
    addLog('info', `Translated ${newChunks} chunk(s). Total: ${newStats.translatedChunks}`)
  }
  
  if (newStats.retries > oldStats.retries) {
    const newRetries = newStats.retries - oldStats.retries
    addLog('warning', `Retried ${newRetries} translation(s). Total retries: ${newStats.retries}`)
  }
  
  if (newStats.errors > oldStats.errors) {
    const newErrors = newStats.errors - oldStats.errors
    addLog('error', `${newErrors} translation error(s) occurred. Total errors: ${newStats.errors}`)
  }
}, { deep: true })

// Add initial log on mount
onMounted(() => {
  addLog('info', 'Translation process started')
})

// Cleanup on unmount
onUnmounted(() => {
  if (logPollingInterval) {
    clearInterval(logPollingInterval)
  }
})
</script>

<style scoped>
.log-console {
  width: 100%;
  max-width: 800px;
  margin: 24px auto;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  background: #f8f9fa;
  font-family: 'Courier New', monospace;
}

.log-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #343a40;
  color: white;
  border-radius: 8px 8px 0 0;
}

.log-header h4 {
  margin: 0;
  font-size: 16px;
}

.clear-btn {
  background: #6c757d;
  color: white;
  border: none;
  padding: 4px 12px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
}

.clear-btn:hover {
  background: #5a6268;
}

.log-content {
  max-height: 300px;
  overflow-y: auto;
  padding: 0;
}

.log-entry {
  display: flex;
  padding: 8px 16px;
  border-bottom: 1px solid #e9ecef;
  font-size: 13px;
  line-height: 1.4;
}

.log-entry:last-child {
  border-bottom: none;
}

.log-timestamp {
  color: #6c757d;
  margin-right: 12px;
  min-width: 80px;
}

.log-level {
  font-weight: bold;
  margin-right: 12px;
  min-width: 60px;
}

.log-message {
  flex: 1;
  word-break: break-word;
}

.log-info {
  background: #ffffff;
}

.log-info .log-level {
  color: #17a2b8;
}

.log-warning {
  background: #fff3cd;
}

.log-warning .log-level {
  color: #856404;
}

.log-error {
  background: #f8d7da;
}

.log-error .log-level {
  color: #721c24;
}

.log-error .log-message {
  color: #721c24;
}

/* Scrollbar styling */
.log-content::-webkit-scrollbar {
  width: 8px;
}

.log-content::-webkit-scrollbar-track {
  background: #f1f1f1;
}

.log-content::-webkit-scrollbar-thumb {
  background: #c1c1c1;
  border-radius: 4px;
}

.log-content::-webkit-scrollbar-thumb:hover {
  background: #a8a8a8;
}
</style>