<template>
  <div v-if="visible" class="modal-overlay" @click="$emit('close')">
    <div class="modal-content" @click.stop>
      <div class="modal-header">
        <h3>
          Job Log
          <span v-if="polling" class="poll-dot" title="Live: refreshing every 2s">●</span>
        </h3>
        <button class="close-btn" @click="$emit('close')">
          <span class="close-icon">×</span>
        </button>
      </div>
      <div class="modal-body">
        <div v-if="!liveJob" class="loading">Loading...</div>
        <div v-else>
          <div class="log-info">
            <div class="info-row">
              <span class="info-label">Clip ID:</span>
              <span class="info-value">{{ liveJob.clip_id }}</span>
            </div>
            <div class="info-row">
              <span class="info-label">Job ID:</span>
              <span class="info-value">{{ liveJob.job_id }}</span>
            </div>
            <div class="info-row">
              <span class="info-label">Status:</span>
              <span :class="['info-value', 'status-pill', liveJob.status]">{{ fmtStatus(liveJob.status) }}</span>
            </div>
          </div>

          <!-- Progress block: only for active / completed jobs (skip pending/failed/cancelled w/o progress) -->
          <div v-if="showProgress" class="progress-block">
            <div class="progress-head">
              <span class="progress-label">{{ progressTitle }}</span>
              <span class="progress-stats">
                <span class="frames">{{ liveJob.progress || 0 }} / {{ liveJob.total || '—' }} frames</span>
                <span v-if="progressPercent !== null" class="pct">{{ progressPercent }}%</span>
              </span>
            </div>
            <div class="progress-bar">
              <div
                :class="['progress', liveJob.status]"
                :style="{ width: (progressPercent ?? 0) + '%' }"
              ></div>
            </div>
            <div v-if="liveJob.status === 'stitching'" class="progress-note">
              All frames rendered. ffmpeg is stitching them into MP4…
            </div>
          </div>

          <div class="log-content">
            <pre ref="logRef" class="log-text">{{ liveJob.log || 'No log available' }}</pre>
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
import { ref, computed, nextTick, watch, onMounted, onUnmounted } from 'vue'
import { fmtStatus } from '../utils.js'
import { fetchJob } from '../api.js'

const props = defineProps({
  visible: Boolean,
  job: Object,
})

const emit = defineEmits(['close'])

const liveJob = ref(null)
const polling = ref(false)
const logRef = ref(null)
let timer = null
const POLL_MS = 2000
const TERMINAL = new Set(['completed', 'failed', 'cancelled'])

const showProgress = computed(() => {
  if (!liveJob.value) return false
  const s = liveJob.value.status
  return s === 'running' || s === 'stitching' || s === 'completed'
})

const progressTitle = computed(() => {
  const s = liveJob.value?.status
  if (s === 'stitching') return 'Stitching MP4'
  if (s === 'completed') return 'Inference complete'
  return 'Running inference'
})

const progressPercent = computed(() => {
  const j = liveJob.value
  if (!j) return null
  if (j.status === 'completed') return 100
  if (j.status === 'stitching') return 100
  const total = Number(j.total) || 0
  const done = Number(j.progress) || 0
  if (!total) return null
  return Math.min(100, Math.max(0, Math.round((done / total) * 100)))
})

async function refresh() {
  const id = liveJob.value?.job_id || props.job?.job_id
  if (!id) return
  try {
    const fresh = await fetchJob(id)
    if (fresh && fresh.job_id) {
      liveJob.value = fresh
      // Stop polling once we hit a terminal state.
      if (TERMINAL.has(fresh.status)) stopPolling()
      // Auto-scroll log to the bottom on new content.
      await nextTick()
      if (logRef.value) logRef.value.scrollTop = logRef.value.scrollHeight
    }
  } catch (e) {
    // Network blip: silently keep polling — next tick may succeed.
    console.warn('LogModal refresh failed:', e?.message || e)
  }
}

function startPolling() {
  if (timer) return
  if (!liveJob.value || TERMINAL.has(liveJob.value.status)) return
  polling.value = true
  timer = setInterval(refresh, POLL_MS)
}

function stopPolling() {
  if (timer) { clearInterval(timer); timer = null }
  polling.value = false
}

function onKeydown(e) {
  if (e.key === 'Escape') emit('close')
}

watch(() => props.visible, async (v) => {
  if (v) {
    // Seed from parent's snapshot, then immediately refresh + start polling.
    liveJob.value = props.job ? { ...props.job } : null
    await refresh()
    startPolling()
  } else {
    stopPolling()
    liveJob.value = null
  }
})

watch(() => props.job?.job_id, async (newId, oldId) => {
  if (!props.visible || newId === oldId) return
  liveJob.value = props.job ? { ...props.job } : null
  stopPolling()
  await refresh()
  startPolling()
})

onMounted(() => {
  window.addEventListener('keydown', onKeydown)
})
onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
  stopPolling()
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
  gap: 16px;
}

.loading {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 300px;
  color: var(--text-muted);
  font-size: 16px;
}

.log-info {
  background: var(--background);
  padding: 16px;
  border-radius: 12px;
  border: 1px solid var(--border);
  margin-bottom: 16px;
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

.progress-block {
  background: var(--background);
  padding: 14px 16px;
  border-radius: 12px;
  border: 1px solid var(--border);
  margin-bottom: 16px;
}

.progress-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 8px;
  gap: 12px;
  flex-wrap: wrap;
}

.progress-label {
  font-size: 13px;
  font-weight: 700;
  color: var(--text);
  letter-spacing: 0.02em;
}

.progress-stats {
  display: inline-flex;
  align-items: baseline;
  gap: 10px;
  font-variant-numeric: tabular-nums;
}

.frames {
  font-size: 12px;
  color: var(--text-muted, #9faac1);
}

.pct {
  font-size: 14px;
  font-weight: 800;
  color: #38bdf8;
}

.progress-bar {
  position: relative;
  width: 100%;
  height: 10px;
  background: rgba(255, 255, 255, 0.06);
  border-radius: 999px;
  overflow: hidden;
}

.progress {
  height: 100%;
  border-radius: 999px;
  transition: width 0.4s var(--ease-out, ease-out);
  background: linear-gradient(90deg, #38bdf8 0%, #c084fc 100%);
}

.progress.running {
  background: linear-gradient(90deg, #38bdf8 0%, #818cf8 100%);
  background-size: 200% 100%;
  animation: shimmer 2.4s linear infinite;
}

.progress.stitching {
  background: linear-gradient(90deg, #c084fc 0%, #f0abfc 100%);
  background-size: 200% 100%;
  animation: shimmer 2.4s linear infinite;
}

.progress.completed {
  background: linear-gradient(90deg, #4ade80 0%, #34d399 100%);
}

@keyframes shimmer {
  0%   { background-position: 0% 0%; }
  100% { background-position: -200% 0%; }
}

.progress-note {
  margin-top: 8px;
  font-size: 11px;
  color: var(--text-muted, #9faac1);
  font-style: italic;
}

.status-pill {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 999px;
  font-weight: 700;
  font-size: 12px;
}

.status-pill.pending    { background: rgba(250, 204, 21, 0.14); color: #facc15; }
.status-pill.running    { background: rgba(56, 189, 248, 0.16); color: #38bdf8; }
.status-pill.stitching  { background: rgba(192, 132, 252, 0.16); color: #c084fc; }
.status-pill.completed  { background: rgba(74, 222, 128, 0.16); color: #4ade80; }
.status-pill.failed     { background: rgba(248, 113, 113, 0.16); color: #f87171; }
.status-pill.cancelled  { background: rgba(251, 146, 60, 0.16); color: #fb923c; }

.poll-dot {
  display: inline-block;
  margin-left: 8px;
  color: #4ade80;
  font-size: 10px;
  animation: pulse 1.4s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 0.35; }
  50% { opacity: 1; }
}

.log-content {
  flex: 1;
  background: var(--background);
  border-radius: 12px;
  border: 1px solid var(--border);
  overflow: hidden;
}

.log-text {
  margin: 0;
  padding: 16px;
  font-family: 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.5;
  color: var(--text);
  white-space: pre-wrap;
  word-wrap: break-word;
  max-height: 500px;
  overflow-y: auto;
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
}

/* 滚动条样式 */
.modal-body::-webkit-scrollbar,
.log-text::-webkit-scrollbar {
  width: 8px;
}

.modal-body::-webkit-scrollbar-track,
.log-text::-webkit-scrollbar-track {
  background: var(--background);
  border-radius: 4px;
}

.modal-body::-webkit-scrollbar-thumb,
.log-text::-webkit-scrollbar-thumb {
  background: var(--border);
  border-radius: 4px;
}

.modal-body::-webkit-scrollbar-thumb:hover,
.log-text::-webkit-scrollbar-thumb:hover {
  background: var(--text-muted);
}
</style>