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
          <span class="meta-label">View:</span>
          <span class="meta-value">{{ formatVisualizationMode(job.visualization_mode) }}</span>
        </div>
        <div class="meta-item meta-path">
          <span class="meta-label">Config:</span>
          <span class="meta-value path-value" :title="job.config || 'Not set'">{{ compactPath(job.config) }}</span>
        </div>
        <div class="meta-item meta-path">
          <span class="meta-label">Checkpoint:</span>
          <span class="meta-value path-value" :title="job.checkpoint || 'Not set'">{{ compactPath(job.checkpoint) }}</span>
        </div>
        <div class="meta-item">
          <span class="meta-label">Created:</span>
          <span class="meta-value">{{ fmtTime(job.created_at) }}</span>
        </div>
        <div class="meta-item" v-if="job.completed_at">
          <span class="meta-label">Completed:</span>
          <span class="meta-value">{{ fmtTime(job.completed_at) }}</span>
        </div>
      </div>
      <div class="card-actions">
        <button v-if="job.status === 'completed'" class="btn-primary" @click.stop="$emit('play-video', job)">
          <span class="btn-icon">▶</span>
          Play
        </button>
        <button class="btn-secondary" @click.stop="$emit('show-log', job)">
          <span class="btn-icon">📋</span>
          Log
        </button>
        <button class="btn-secondary delete-btn" @click.stop="$emit('delete', job.job_id)">
          <span class="btn-icon">🗑</span>
          Delete
        </button>
      </div>
    </div>
  </article>
</template>

<script setup>
import { fmtStatus, fmtTime } from '../utils.js'

const props = defineProps({
  job: Object
})

const emit = defineEmits(['play-video', 'show-log', 'delete'])

function resolveImgSrc(path) {
  if (!path) return 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjEyMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB4PSIwIiB5PSIwIiB3aWR0aD0iMjAwIiBoZWlnaHQ9IjEyMCIgZmlsbD0iIzMzMzMiLz48cGF0aCBkPSJNNzAgMTBsLTU1IDMzIDU1IDMzIDU1LTMzIiBmaWxsPSIjNjY2Ii8+PC9zdmc+'
  return path
}

function cardClick() {
  if (props.job.status === 'completed') {
    emit('play-video', props.job)
  }
}

function compactPath(path) {
  if (!path) return 'Not set'
  const parts = path.split('/')
  if (parts.length <= 2) return path
  return `${parts[0]}/…/${parts[parts.length - 1]}`
}

function formatVisualizationMode(mode) {
  if (mode === 'forward_points') return 'Forward point cloud'
  return 'BEV + 6 cameras'
}
</script>

<style scoped>
.card {
  position: relative;
  background: var(--card-bg);
  border-radius: 20px;
  border: 1px solid var(--border);
  overflow: hidden;
  box-shadow: var(--shadow);
  transition: all .24s var(--ease-out);
  cursor: default;
}

.card:hover {
  transform: translateY(-4px);
  border-color: var(--card-hover-border);
}

.card.clickable {
  cursor: pointer;
}

.card-image {
  position: relative;
  height: 180px;
  overflow: hidden;
  background: #0a0d16;
}

.thumb {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform .3s var(--ease-out);
}

.card:hover .thumb {
  transform: scale(1.05);
}

.status-badge {
  position: absolute;
  top: 12px;
  right: 12px;
  padding: 6px 12px;
  border-radius: 20px;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .06em;
  z-index: 1;
  backdrop-filter: blur(8px);
}

.status-badge.pending {
  background: rgba(255, 193, 7, 0.14);
  color: #ffc107;
  border: 1px solid rgba(255, 193, 7, 0.24);
}

.status-badge.running {
  background: rgba(0, 123, 255, 0.14);
  color: #007bff;
  border: 1px solid rgba(0, 123, 255, 0.24);
}

.status-badge.stitching {
  background: rgba(108, 117, 125, 0.14);
  color: #6c757d;
  border: 1px solid rgba(108, 117, 125, 0.24);
}

.status-badge.completed {
  background: var(--result-done-bg, rgba(255, 241, 118, 0.2));
  color: var(--result-done, #fff176);
  border: 1px solid var(--result-done-border, rgba(255, 245, 150, 0.45));
}

.status-badge.failed {
  background: rgba(220, 53, 69, 0.14);
  color: #dc3545;
  border: 1px solid rgba(220, 53, 69, 0.24);
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
  background: var(--accent);
  transition: width .3s ease;
  animation: progress 2s ease-in-out infinite;
}

@keyframes progress {
  0%, 100% { width: 0%; }
  50% { width: 100%; }
}

.card-content {
  padding: 18px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 14px;
}

.clip-id {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  color: var(--text);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.job-id {
  font-size: 11px;
  color: var(--muted);
  background: var(--panel-alt);
  padding: 4px 10px;
  border-radius: 8px;
  margin-left: 10px;
  white-space: nowrap;
  font-weight: 600;
}

.card-meta {
  margin-bottom: 18px;
  font-size: 13px;
  color: var(--muted);
}

.meta-item {
  display: flex;
  justify-content: space-between;
  margin-bottom: 6px;
  gap: 10px;
}

.meta-label {
  color: var(--muted);
}

.meta-value {
  color: var(--text);
  font-weight: 600;
}

.meta-path {
  align-items: flex-start;
}

.path-value {
  max-width: 190px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  text-align: right;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
  font-size: 11px;
  color: var(--accent);
}

.card-actions {
  display: flex;
  gap: 10px;
}

.card-actions button {
  flex: 1;
  padding: 10px 12px;
  font-size: 13px;
}

.delete-btn:hover {
  color: var(--danger);
  border-color: var(--danger);
  background: rgba(220, 53, 69, 0.08);
}

.btn-icon {
  font-size: 14px;
  line-height: 1;
}

@media (max-width: 768px) {
  .card-actions {
    flex-direction: column;
  }
}
</style>
