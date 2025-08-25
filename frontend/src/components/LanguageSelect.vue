<template>
  <div class="language-select">
    <label for="language">Target Language</label>
    <select
      id="language"
      :value="modelValue"
      @change="handleChange"
      class="language-dropdown"
    >
      <option value="" disabled>Select target language</option>
      <option 
        v-for="language in languages" 
        :key="language.code" 
        :value="language.code"
      >
        {{ language.flag }} {{ language.name }}
      </option>
    </select>
  </div>
</template>

<script setup lang="ts">
interface Language {
  code: string
  name: string
  flag: string
}

interface Props {
  modelValue: string
}

const props = defineProps<Props>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const languages: Language[] = [
  { code: 'zh-TW', name: '繁體中文', flag: '🇹🇼' },
  { code: 'zh-CN', name: '简体中文', flag: '🇨🇳' },
  { code: 'en', name: 'English', flag: '🇺🇸' },
  { code: 'ja', name: '日本語', flag: '🇯🇵' },
  { code: 'ko', name: '한국어', flag: '🇰🇷' },
  { code: 'fr', name: 'Français', flag: '🇫🇷' },
  { code: 'de', name: 'Deutsch', flag: '🇩🇪' },
  { code: 'es', name: 'Español', flag: '🇪🇸' },
  { code: 'pt', name: 'Português', flag: '🇵🇹' },
  { code: 'it', name: 'Italiano', flag: '🇮🇹' },
  { code: 'ru', name: 'Русский', flag: '🇷🇺' },
  { code: 'ar', name: 'العربية', flag: '🇸🇦' }
]

function handleChange(event: Event) {
  const target = event.target as HTMLSelectElement
  emit('update:modelValue', target.value)
}
</script>

<style scoped>
.language-select {
  margin-bottom: 24px;
}

.language-select label {
  display: block;
  margin-bottom: 8px;
  font-weight: 600;
  color: #333;
  font-size: 16px;
}

.language-dropdown {
  width: 100%;
  padding: 12px 16px;
  border: 2px solid #ddd;
  border-radius: 8px;
  font-size: 16px;
  background: white;
  cursor: pointer;
  transition: border-color 0.3s ease;
}

.language-dropdown:focus {
  outline: none;
  border-color: #007bff;
  box-shadow: 0 0 0 3px rgba(0, 123, 255, 0.1);
}

.language-dropdown:hover {
  border-color: #007bff;
}

.language-dropdown option {
  padding: 8px;
  font-size: 16px;
}
</style>