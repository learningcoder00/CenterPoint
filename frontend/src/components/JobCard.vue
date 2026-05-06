<template>
  <article :class="['card', { clickable: job.status === 'completed' }]" @click="cardClick">
    <div class="card-image">
      <img class="thumb" loading="lazy" :src="resolveImgSrc(job.thumbnail_path)" :alt="job.clip_id">
      <button
        v-if="showStarToggle"
        type="button"
        :class="['star-btn', { starred: job.starred }]"
        :title="job.starred ? 'Unstar job' : 'Star job'"
        :aria-pressed="!!job.starred"
        @click.stop="$emit('toggle-star', job)"
      >
        <span class="star-icon">{{ job.starred ? '★' : '☆' }}</span>
      </button>
      <div
        v-if="showReview"
        :class="['review-badge', reviewClass, { 'review-badge--shifted': showStarToggle }]"
      >
        <span class="review-dot" aria-hidden="true"></span>
        {{ reviewLabel }}
      </div>
      <div :class="['status-badge', job.status]">{{ fmtStatus(job.status) }}</div>
      <div
        v-if="isInterruptedFailure"
        class="interrupted-badge"
        title="Job was interrupted because the server restarted before it finished. Resubmit to rerun."
      >
        ⟳ Server interrupted
      </div>
      <div v-if="isCompareJob" class="compare-badge" title="A vs B BEV compare job">
        <span class="compare-badge__a">A</span>
        <span class="compare-badge__sep">⇆</span>
        <span class="compare-badge__b">B</span>
      </div>
      <div v-if="job.status === 'running' || job.status === 'stitching'" class="progress-bar">
        <div class="progress" :style="{ width: '50%' }"></div>
      </div>
    </div>
    <div class="card-content">
      <div class="card-header">
        <h3 class="clip-id">{{ job.clip_id }}</h3>
        <div class="header-right">
          <div class="job-id">{{ job.job_id }}</div>
        </div>
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
        <template v-if="isCompareJob">
          <div class="meta-item meta-path">
            <span class="meta-label">Config B:</span>
            <span class="meta-value path-value" :title="job.config_b || 'Not set'">{{ compactPath(job.config_b) }}</span>
          </div>
          <div class="meta-item meta-path">
            <span class="meta-label">Checkpoint B:</span>
            <span class="meta-value path-value" :title="job.checkpoint_b || 'Not set'">{{ compactPath(job.checkpoint_b) }}</span>
          </div>
        </template>
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
        <button
          class="btn-secondary delete-btn"
          title="Delete job"
          @click.stop="$emit('delete', job.job_id)"
        >
          <span class="btn-icon">🗑</span>
          Delete
        </button>
      </div>
    </div>
  </article>
</template>

<script setup>
import { computed } from 'vue'
import { fmtStatus, fmtTime } from '../utils.js'

const props = defineProps({
  job: Object,
  showReview: { type: Boolean, default: false },
  showStarToggle: { type: Boolean, default: false },
})

const emit = defineEmits(['play-video', 'show-log', 'delete', 'toggle-star'])

const reviewClass = computed(() => {
  const s = props.job?.review_status || 'unreviewed'
  if (s === 'has_issue') return 'issue'
  if (s === 'no_issue') return 'clean'
  return 'pending'
})

const reviewLabel = computed(() => {
  const s = props.job?.review_status || 'unreviewed'
  if (s === 'has_issue') return 'Issue'
  if (s === 'no_issue') return 'Clean'
  return 'Pending'
})

const isCompareJob = computed(() => props.job?.visualization_mode === 'bev_compare')

const isInterruptedFailure = computed(() => {
  if (props.job?.status !== 'failed') return false
  const log = props.job?.log || ''
  return log.includes('[recovery]')
})

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
  if (mode === 'bev_compare') return 'BEV compare (A vs B)'
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

.review-badge {
  position: absolute;
  top: 12px;
  left: 12px;
  transition: left .18s var(--ease-out);
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 11px 5px 9px;
  border-radius: 999px;
  font-size: 10.5px;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  z-index: 2;
  backdrop-filter: blur(10px);
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.18);
}

.review-badge .review-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
  box-shadow: 0 0 8px currentColor;
}

.review-badge.issue {
  background: rgba(248, 113, 113, 0.18);
  color: #f87171;
  border: 1px solid rgba(248, 113, 113, 0.4);
}

.review-badge.clean {
  background: rgba(74, 222, 128, 0.16);
  color: #4ade80;
  border: 1px solid rgba(74, 222, 128, 0.36);
}

.review-badge.pending {
  background: rgba(148, 163, 184, 0.18);
  color: #cbd5e1;
  border: 1px solid rgba(148, 163, 184, 0.32);
}

.review-badge--shifted {
  left: 58px;
}

.star-btn {
  position: absolute;
  top: 10px;
  left: 12px;
  z-index: 3;
  width: 36px;
  height: 36px;
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.18);
  background: rgba(10, 13, 22, 0.55);
  color: rgba(255, 255, 255, 0.85);
  font-size: 18px;
  line-height: 1;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  backdrop-filter: blur(10px);
  transition:
    transform 0.18s var(--ease-out),
    border-color 0.18s var(--ease-out),
    background 0.18s var(--ease-out),
    color 0.18s var(--ease-out),
    box-shadow 0.22s var(--ease-out);
}

.star-btn .star-icon {
  display: inline-block;
  transition: transform 0.22s var(--ease-out);
}

.star-btn:hover {
  transform: translateY(-1px);
  border-color: rgba(253, 224, 71, 0.55);
  color: #fde047;
}

.star-btn:hover .star-icon {
  transform: scale(1.12) rotate(-6deg);
}

.star-btn.starred {
  color: #fde047;
  background: linear-gradient(180deg, rgba(253, 224, 71, 0.28), rgba(234, 179, 8, 0.18));
  border-color: rgba(253, 224, 71, 0.6);
  box-shadow:
    0 0 0 1px rgba(253, 224, 71, 0.18),
    0 8px 22px rgba(253, 224, 71, 0.28);
}

.star-btn.starred .star-icon {
  text-shadow:
    0 0 8px rgba(253, 224, 71, 0.7),
    0 0 18px rgba(253, 224, 71, 0.35);
  animation: starPop 0.45s var(--ease-out);
}

@keyframes starPop {
  0% { transform: scale(0.6); opacity: 0.4; }
  60% { transform: scale(1.25) rotate(8deg); opacity: 1; }
  100% { transform: scale(1) rotate(0); opacity: 1; }
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

.interrupted-badge {
  position: absolute;
  top: 56px;
  right: 12px;
  z-index: 2;
  padding: 5px 10px;
  border-radius: 999px;
  font-size: 10.5px;
  font-weight: 800;
  letter-spacing: .04em;
  color: #fef2f2;
  background: linear-gradient(135deg, rgba(220, 38, 38, 0.92), rgba(248, 113, 113, 0.85));
  border: 1px solid rgba(254, 226, 226, 0.5);
  box-shadow: 0 6px 18px rgba(220, 38, 38, 0.32);
  cursor: help;
  backdrop-filter: blur(8px);
}

.compare-badge {
  position: absolute;
  bottom: 12px;
  left: 12px;
  z-index: 2;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 9px;
  border-radius: 999px;
  font-size: 10.5px;
  font-weight: 800;
  letter-spacing: .04em;
  background: linear-gradient(135deg, rgba(56, 189, 248, 0.92), rgba(244, 114, 182, 0.92));
  color: #0a0d16;
  border: 1px solid rgba(255, 255, 255, 0.35);
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.28);
  backdrop-filter: blur(8px);
}
.compare-badge__a { color: #053f5c; }
.compare-badge__b { color: #5b1e3f; }
.compare-badge__sep { font-size: 11px; opacity: .85; }

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

.header-right { display:flex; align-items:center; gap:8px; }

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
