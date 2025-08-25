<template>
  <div class="progress-container">
    <div class="progress-header">
      <h3>Translation Progress</h3>
      <span class="progress-percentage">{{ progress }}%</span>
    </div>
    
    <div class="progress-bar">
      <div 
        class="progress-fill" 
        :style="{ width: `${progress}%` }"
        :class="{ 'complete': progress >= 100, 'error': status === 'error' }"
      ></div>
    </div>
    
    <div class="progress-details">
      <div class="current-item">
        <span v-if="current && current.type === 'epub'" class="item-type">📖 EPUB</span>
        <span v-else-if="current && current.type === 'pdf'" class="item-type">📄 PDF</span>
        
        <span v-if="current && current.chapter" class="current-chapter">
          {{ current.chapter }}
        </span>
        <span v-else-if="current && current.page" class="current-page">
          Page {{ current.page }}
        </span>
      </div>
      
      <div class="stats" v-if="stats">
        <div class="stat-item">
          <span class="stat-label">Translated:</span>
          <span class="stat-value">{{ stats.translatedChunks }}</span>
        </div>
        <div class="stat-item" v-if="stats.retries > 0">
          <span class="stat-label">Retries:</span>
          <span class="stat-value">{{ stats.retries }}</span>
        </div>
        <div class="stat-item" v-if="stats.errors > 0">
          <span class="stat-label">Errors:</span>
          <span class="stat-value error-count">{{ stats.errors }}</span>
        </div>
      </div>
    </div>
    
    <div class="status-message">
      <span 
        class="status-badge" 
        :class="statusClass"
      >
        {{ statusText }}
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { CurrentProgress, JobStats } from '../types'

interface Props {
  progress: number
  status: 'running' | 'done' | 'error' | 'canceled'
  current?: CurrentProgress
  stats?: JobStats
}

const props = defineProps<Props>()

const statusClass = computed(() => ({
  'status-running': props.status === 'running',
  'status-done': props.status === 'done',
  'status-error': props.status === 'error',
  'status-canceled': props.status === 'canceled'
}))

const statusText = computed(() => {
  switch (props.status) {
    case 'running':
      return 'Processing...'
    case 'done':
      return 'Completed'
    case 'error':
      return 'Error'
    case 'canceled':
      return 'Canceled'
    default:
      return 'Unknown'
  }
})
</script>

<style scoped>
.progress-container {
  width: 100%;
  max-width: 600px;
  margin: 24px auto;
  padding: 24px;
  border: 1px solid #e0e0e0;
  border-radius: 12px;
  background: white;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.progress-header h3 {
  margin: 0;
  font-size: 20px;
  color: #333;
}

.progress-percentage {
  font-size: 24px;
  font-weight: bold;
  color: #007bff;
}

.progress-bar {
  width: 100%;
  height: 12px;
  background: #f0f0f0;
  border-radius: 6px;
  overflow: hidden;
  margin-bottom: 16px;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #007bff, #0056b3);
  border-radius: 6px;
  transition: width 0.3s ease;
  position: relative;
}

.progress-fill.complete {
  background: linear-gradient(90deg, #28a745, #1e7e34);
}

.progress-fill.error {
  background: linear-gradient(90deg, #dc3545, #bd2130);
}

.progress-details {
  margin-bottom: 16px;
}

.current-item {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
  font-size: 16px;
}

.item-type {
  font-weight: 600;
  color: #666;
}

.current-chapter,
.current-page {
  color: #333;
  font-weight: 500;
}

.stats {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 14px;
}

.stat-label {
  color: #666;
}

.stat-value {
  font-weight: 600;
  color: #333;
}

.error-count {
  color: #dc3545;
}

.status-message {
  text-align: center;
}

.status-badge {
  padding: 8px 16px;
  border-radius: 20px;
  font-weight: 600;
  font-size: 14px;
}

.status-running {
  background: #e3f2fd;
  color: #1976d2;
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
</style>