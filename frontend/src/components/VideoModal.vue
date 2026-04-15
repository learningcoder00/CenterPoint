<template>
  <div v-if="visible" class="modal-overlay" @click="$emit('close')">
    <div class="modal-content" @click.stop>
      <div class="modal-header">
        <h3>Video Playback</h3>
        <button class="close-btn" @click="$emit('close')">
          <span class="close-icon">×</span>
        </button>
      </div>
      <div class="modal-body">
        <div v-if="!job" class="loading">Loading...</div>
        <div v-else>
          <div class="video-container">
            <video ref="videoRef" controls autoplay class="video-player">
              <source :src="videoSrc" type="video/mp4">
              Your browser does not support the video tag.
            </video>
          </div>
          <div class="video-info">
            <div class="info-row">
              <span class="info-label">Clip ID:</span>
              <span class="info-value">{{ job.clip_id }}</span>
            </div>
            <div class="info-row">
              <span class="info-label">Job ID:</span>
              <span class="info-value">{{ job.job_id }}</span>
            </div>
            <div class="info-row">
              <span class="info-label">Status:</span>
              <span class="info-value">{{ fmtStatus(job.status) }}</span>
            </div>
            <div class="info-row" v-if="job.completed_at">
              <span class="info-label">Completed:</span>
              <span class="info-value">{{ fmtTime(job.completed_at) }}</span>
            </div>
          </div>
        </div>
      </div>
      <div class="modal-footer">
        <button class="btn-close" @click="$emit('close')">Close</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, ref, watch, onMounted, onUnmounted } from 'vue'
import { fmtStatus, fmtTime } from '../utils.js'
import { videoUrl } from '../api.js'

const props = defineProps({
  visible: Boolean,
  job: Object
})

const emit = defineEmits(['close'])
const videoRef = ref(null)
const videoSrc = computed(() => {
  const jobId = props.job?.job_id
  return jobId ? videoUrl(jobId) : ''
})

function onKeydown(e) {
  if (e.key === 'Escape') {
    emit('close')
  }
}

watch(
  () => [props.visible, props.job?.job_id],
  async ([visible]) => {
    if (!visible) {
      if (videoRef.value) videoRef.value.pause()
      return
    }
    await nextTick()
    if (!videoRef.value || !videoSrc.value) return
    videoRef.value.load()
    videoRef.value.play().catch(e => console.log('Video play failed:', e))
  }
)

onMounted(() => {
  window.addEventListener('keydown', onKeydown)
})
onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
  if (videoRef.value) {
    videoRef.value.pause()
  }
})
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.8);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  animation: fadeIn 0.3s ease;
}

.modal-content {
  background: var(--panel);
  border-radius: 16px;
  border: 1px solid var(--border);
  width: 90%;
  max-width: 900px;
  max-height: 90vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  animation: slideIn 0.3s ease;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  border-bottom: 1px solid var(--border);
  background: var(--background);
}

.modal-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: var(--text);
}

.close-btn {
  background: none;
  border: none;
  color: var(--text-muted);
  font-size: 24px;
  cursor: pointer;
  padding: 0;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  transition: all 0.3s ease;
}

.close-btn:hover {
  background: rgba(255, 255, 255, 0.1);
  color: var(--text);
}

.close-icon {
  line-height: 1;
}

.modal-body {
  flex: 1;
  padding: 24px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.loading {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 300px;
  color: var(--text-muted);
  font-size: 16px;
}

.video-container {
  position: relative;
  padding-bottom: 56.25%;
  height: 0;
  overflow: hidden;
  border-radius: 12px;
  background: var(--background);
}

.video-player {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  border: none;
  border-radius: 12px;
}

.video-info {
  background: var(--background);
  padding: 16px;
  border-radius: 12px;
  border: 1px solid var(--border);
}

.info-row {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border);
}

.info-row:last-child {
  margin-bottom: 0;
  padding-bottom: 0;
  border-bottom: none;
}

.info-label {
  font-size: 13px;
  color: var(--text-muted);
  font-weight: 500;
}

.info-value {
  font-size: 13px;
  color: var(--text);
  font-weight: 600;
  text-align: right;
  flex: 1;
  margin-left: 16px;
  word-break: break-all;
}

.modal-footer {
  padding: 16px 24px;
  border-top: 1px solid var(--border);
  background: var(--background);
  display: flex;
  justify-content: flex-end;
}

.btn-close {
  padding: 10px 20px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--panel);
  color: var(--text);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.3s ease;
}

.btn-close:hover {
  background: rgba(255, 255, 255, 0.08);
  transform: translateY(-1px);
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (max-width: 768px) {
  .modal-content {
    width: 95%;
    max-height: 95vh;
  }
  
  .modal-header,
  .modal-footer {
    padding: 12px 16px;
  }
  
  .modal-body {
    padding: 16px;
  }
  
  .video-container {
    padding-bottom: 56.25%;
  }
}

/* 滚动条样式 */
.modal-body::-webkit-scrollbar {
  width: 8px;
}

.modal-body::-webkit-scrollbar-track {
  background: var(--background);
  border-radius: 4px;
}

.modal-body::-webkit-scrollbar-thumb {
  background: var(--border);
  border-radius: 4px;
}

.modal-body::-webkit-scrollbar-thumb:hover {
  background: var(--text-muted);
}
</style>