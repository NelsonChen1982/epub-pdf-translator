<template>
  <div class="file-picker">
    <div 
      class="drop-zone"
      :class="{ 'drag-over': isDragOver, 'has-file': selectedFile }"
      @dragover.prevent="handleDragOver"
      @dragleave.prevent="handleDragLeave"
      @drop.prevent="handleDrop"
      @click="openFileDialog"
    >
      <input
        ref="fileInput"
        type="file"
        :accept="acceptedTypes"
        @change="handleFileSelect"
        style="display: none"
      />
      
      <div v-if="!selectedFile" class="upload-prompt">
        <div class="upload-icon">📚</div>
        <h3>Upload Document</h3>
        <p>Drag & drop your EPUB or PDF file here, or click to browse</p>
        <div class="file-types">
          <span class="file-type">EPUB</span>
          <span class="file-type">PDF</span>
        </div>
        <p class="size-limit">Max file size: {{ maxSizeMB }}MB</p>
      </div>
      
      <div v-else class="file-info">
        <div class="file-icon">
          {{ selectedFile.name.toLowerCase().endsWith('.epub') ? '📖' : '📄' }}
        </div>
        <div class="file-details">
          <h4>{{ selectedFile.name }}</h4>
          <p>{{ formatFileSize(selectedFile.size) }}</p>
          <button class="remove-btn" @click.stop="removeFile">Remove</button>
        </div>
      </div>
    </div>
    
    <div v-if="error" class="error-message">
      {{ error }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

interface Props {
  maxSize?: number
}

const props = withDefaults(defineProps<Props>(), {
  maxSize: 104857600 // 100MB
})

const emit = defineEmits<{
  fileSelected: [file: File]
  fileRemoved: []
}>()

const fileInput = ref<HTMLInputElement>()
const selectedFile = ref<File | null>(null)
const isDragOver = ref(false)
const error = ref('')

const acceptedTypes = '.epub,.pdf'
const maxSizeMB = computed(() => Math.round(props.maxSize / 1024 / 1024))

function validateFile(file: File): string | null {
  const allowedTypes = ['.epub', '.pdf']
  const fileExt = '.' + file.name.split('.').pop()?.toLowerCase()
  
  if (!allowedTypes.includes(fileExt)) {
    return 'Only EPUB and PDF files are allowed'
  }
  
  if (file.size > props.maxSize) {
    return `File too large. Maximum size is ${maxSizeMB.value}MB`
  }
  
  return null
}

function handleFile(file: File) {
  const validationError = validateFile(file)
  
  if (validationError) {
    error.value = validationError
    return
  }
  
  error.value = ''
  selectedFile.value = file
  emit('fileSelected', file)
}

function handleFileSelect(event: Event) {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  
  if (file) {
    handleFile(file)
  }
}

function handleDrop(event: DragEvent) {
  isDragOver.value = false
  const files = event.dataTransfer?.files
  
  if (files && files.length > 0) {
    handleFile(files[0])
  }
}

function handleDragOver() {
  isDragOver.value = true
}

function handleDragLeave() {
  isDragOver.value = false
}

function openFileDialog() {
  fileInput.value?.click()
}

function removeFile() {
  selectedFile.value = null
  error.value = ''
  if (fileInput.value) {
    fileInput.value.value = ''
  }
  emit('fileRemoved')
}

function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 Bytes'
  
  const k = 1024
  const sizes = ['Bytes', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}
</script>

<style scoped>
.file-picker {
  width: 100%;
  max-width: 500px;
  margin: 0 auto;
}

.drop-zone {
  border: 2px dashed #ccc;
  border-radius: 12px;
  padding: 40px 20px;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s ease;
  background: #fafafa;
}

.drop-zone:hover {
  border-color: #007bff;
  background: #f0f8ff;
}

.drop-zone.drag-over {
  border-color: #007bff;
  background: #e6f3ff;
  transform: scale(1.02);
}

.drop-zone.has-file {
  border-color: #28a745;
  background: #f0fff0;
}

.upload-prompt {
  color: #666;
}

.upload-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.upload-prompt h3 {
  margin: 0 0 8px 0;
  color: #333;
  font-size: 24px;
}

.upload-prompt p {
  margin: 8px 0;
  font-size: 16px;
}

.file-types {
  display: flex;
  justify-content: center;
  gap: 12px;
  margin: 16px 0;
}

.file-type {
  background: #007bff;
  color: white;
  padding: 4px 12px;
  border-radius: 16px;
  font-size: 14px;
  font-weight: 500;
}

.size-limit {
  font-size: 14px;
  color: #888;
}

.file-info {
  display: flex;
  align-items: center;
  gap: 16px;
}

.file-icon {
  font-size: 32px;
}

.file-details {
  text-align: left;
  flex: 1;
}

.file-details h4 {
  margin: 0 0 4px 0;
  color: #333;
  font-size: 18px;
}

.file-details p {
  margin: 0 0 8px 0;
  color: #666;
  font-size: 14px;
}

.remove-btn {
  background: #dc3545;
  color: white;
  border: none;
  padding: 6px 12px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
}

.remove-btn:hover {
  background: #c82333;
}

.error-message {
  margin-top: 12px;
  padding: 12px;
  background: #f8d7da;
  color: #721c24;
  border: 1px solid #f5c6cb;
  border-radius: 4px;
  font-size: 14px;
}
</style>