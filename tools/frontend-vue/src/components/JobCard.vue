<template>
  <article :class="['card', { clickable: job.status === 'completed' }]" @click="cardClick">
    <div class="card-image">
      <img class="thumb" loading="lazy" :src="resolveImgSrc(job.thumbnail_path)" :alt="job.clip_id">
      <div :class="['status-badge', job.status]">{{ fmtStatus(job.status) }}</div>
      <div v-if="job.status === 'running' || job.status === 'stitching'" class="progress-bar">
        <div class="progress" :style="{ width: '50%' }"></div>
      </div>
    </div>
    <div class="card-content">
      <div class="card-header">
        <h3 class="clip-id">{{ job.clip_id }}</h3>
        <div class="job-id">{{ job.job_id }}</div>
      </div>
      <div class="card-meta">
        <div class="meta-item">
          <span class="meta-label">Created:</span>
          <span class="meta-value">{{ formatTime(job.created_at) }}</span>
        </div>
        <div class="meta-item" v-if="job.completed_at">
          <span class="meta-label">Completed:</span>
          <span class="meta-value">{{ formatTime(job.completed_at) }}</span>
        </div>
      </div>
      <div class="card-actions">
        <button v-if="job.status === 'completed'" class="action-btn play" @click.stop="$emit('play-video', job)">
          <span class="btn-icon">▶</span>
          Play
        </button>
        <button class="action-btn log" @click.stop="$emit('show-log', job)">
          <span class="btn-icon">📋</span>
          Log
        </button>
        <button class="action-btn delete" @click.stop="$emit('delete', job.job_id)">
          <span class="btn-icon">🗑</span>
          Delete
        </button>
      </div>
    </div>
  </article>
</template>

<script setup>
import { fmtStatus } from '../utils.js'

const props = defineProps({
  job: Object
})

const emit = defineEmits(['play-video', 'show-log', 'delete'])

function resolveImgSrc(path) {
  if (!path) return 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjEyMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB4PSIwIiB5PSIwIiB3aWR0aD0iMjAwIiBoZWlnaHQ9IjEyMCIgZmlsbD0iIzMzMzMiLz48cGF0aCBkPSJNNzAgMTBsLTU1IDMzIDU1IDMzIDU1LTMzIiBmaWxsPSIjNjY2Ii8+PC9zdmc+'
  return path
}

function formatTime(t) {
  if (!t) return ''
  return new Date(t).toLocaleString()
}

function cardClick() {
  if (props.job.status === 'completed') {
    emit('play-video', props.job)
  }
}
</script>

<style scoped>
.card {
  background: var(--panel);
  border-radius: 16px;
  border: 1px solid var(--border);
  overflow: hidden;
  box-shadow: var(--shadow);
  transition: all .3s ease;
  cursor: default;
}

.card:hover {
  transform: translateY(-4px);
  box-shadow: 0 12px 24px rgba(0,0,0,.2);
}

.card.clickable {
  cursor: pointer;
}

.card-image {
  position: relative;
  height: 180px;
  overflow: hidden;
  background: var(--background);
}

.thumb {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform .3s ease;
}

.card:hover .thumb {
  transform: scale(1.05);
}

.status-badge {
  position: absolute;
  top: 12px;
  right: 12px;
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: .5px;
  z-index: 1;
}

.status-badge.pending {
  background: rgba(255, 193, 7, 0.2);
  color: #ffc107;
  border: 1px solid rgba(255, 193, 7, 0.4);
}

.status-badge.running {
  background: rgba(0, 123, 255, 0.2);
  color: #007bff;
  border: 1px solid rgba(0, 123, 255, 0.4);
}

.status-badge.stitching {
  background: rgba(108, 117, 125, 0.2);
  color: #6c757d;
  border: 1px solid rgba(108, 117, 125, 0.4);
}

.status-badge.completed {
  background: rgba(25, 135, 84, 0.2);
  color: #198754;
  border: 1px solid rgba(25, 135, 84, 0.4);
}

.status-badge.failed {
  background: rgba(220, 53, 69, 0.2);
  color: #dc3545;
  border: 1px solid rgba(220, 53, 69, 0.4);
}

.progress-bar {
  position: absolute;
  bottom: 0;
  left: 0;
  width: 100%;
  height: 4px;
  background: rgba(0,0,0,.2);
  overflow: hidden;
}

.progress {
  height: 100%;
  background: var(--primary);
  transition: width .3s ease;
  animation: progress 2s ease-in-out infinite;
}

@keyframes progress {
  0%, 100% { width: 0%; }
  50% { width: 100%; }
}

.card-content {
  padding: 16px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
}

.clip-id {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--text);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.job-id {
  font-size: 12px;
  color: var(--text-muted);
  background: rgba(255,255,255,.05);
  padding: 2px 8px;
  border-radius: 4px;
  margin-left: 8px;
  white-space: nowrap;
}

.card-meta {
  margin-bottom: 16px;
  font-size: 12px;
  color: var(--text-muted);
}

.meta-item {
  display: flex;
  justify-content: space-between;
  margin-bottom: 4px;
}

.meta-label {
  color: var(--text-muted);
}

.meta-value {
  color: var(--text);
  font-weight: 500;
}

.card-actions {
  display: flex;
  gap: 8px;
}

.action-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: transparent;
  color: var(--text);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all .3s ease;
}

.action-btn:hover {
  background: rgba(255,255,255,.08);
  transform: translateY(-1px);
}

.action-btn.play {
  background: var(--primary);
  color: white;
  border-color: var(--primary);
}

.action-btn.play:hover {
  background: rgba(59, 130, 246, 0.9);
}

.action-btn.log {
  background: rgba(108, 117, 125, 0.2);
  color: #6c757d;
  border-color: rgba(108, 117, 125, 0.4);
}

.action-btn.log:hover {
  background: rgba(108, 117, 125, 0.3);
}

.action-btn.delete {
  background: rgba(220, 53, 69, 0.2);
  color: #dc3545;
  border-color: rgba(220, 53, 69, 0.4);
}

.action-btn.delete:hover {
  background: rgba(220, 53, 69, 0.3);
}

.btn-icon {
  font-size: 14px;
  line-height: 1;
}

@media (max-width: 768px) {
  .card-actions {
    flex-direction: column;
  }
  
  .action-btn {
    width: 100%;
  }
}
</style>