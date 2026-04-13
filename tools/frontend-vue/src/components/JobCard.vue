<template>
  <article :class="['card', { clickable: job.status === 'completed' }]" @click="cardClick">
    <img class="thumb" loading="lazy" :src="resolveImgSrc(job.thumbnail_path)" :alt="job.clip_id">
    <span :class="['status-badge', job.status]">
      <span v-if="isActive" class="spinner"></span>{{ fmtStatus(job.status) }}
    </span>
    <div class="progress-wrap">
      <div class="progress-bar" :style="progressStyle"></div>
    </div>
    <div class="card-body">
      <div class="card-header">
        <h2 class="card-title">{{ job.clip_id }}</h2>
        <span class="badge">{{ job.frame_count || '—' }} frames</span>
      </div>
      <div class="meta">
        <div class="meta-item"><span class="label">Status</span><span class="value">{{ fmtStatus(job.status) }}{{ pctText }}</span></div>
        <div class="meta-item"><span class="label">Created</span><span class="value">{{ fmtTime(job.created_at) }}</span></div>
        <div class="meta-item" style="grid-column:1/-1"><span class="label">Config</span><span class="value">{{ fmtPath(job.config) }}</span></div>
        <div class="meta-item" style="grid-column:1/-1"><span class="label">Checkpoint</span><span class="value">{{ fmtPath(job.checkpoint) }}</span></div>
      </div>
    </div>
    <div class="card-footer">
      <span class="log-line" title="点击查看完整日志" @click.stop="$emit('show-log', job)">{{ lastLogLine }}</span>
      <div class="action-buttons">
        <button class="ai-btn" @click.stop="goToAIOptimization">AI优化</button>
        <button class="delete-btn" @click.stop="$emit('delete', job.job_id)">删除</button>
      </div>
    </div>
  </article>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { resolveImgSrc } from '../api.js'
import { fmtStatus, fmtTime, fmtPath } from '../utils.js'

const props = defineProps({ job: Object })
const emit = defineEmits(['play-video', 'show-log', 'delete'])
const router = useRouter()

const isActive = computed(() => props.job.status === 'running' || props.job.status === 'stitching')
const pct = computed(() => props.job.total > 0 ? Math.round((props.job.progress / props.job.total) * 100) : 0)
const pctText = computed(() => props.job.total > 0 ? ` (${pct.value}%)` : '')

const progressStyle = computed(() => {
  const w = props.job.status === 'completed' ? 100 : pct.value
  let bg = 'var(--running)'
  if (props.job.status === 'completed') bg = 'var(--success)'
  else if (props.job.status === 'failed') bg = 'var(--danger)'
  return { width: w + '%', background: bg }
})

const lastLogLine = computed(() => {
  const lines = (props.job.log || '').trim().split('\n').filter(Boolean)
  return lines[lines.length - 1] || '—'
})

function cardClick() {
  if (props.job.status === 'completed') emit('play-video', props.job)
}

function goToAIOptimization() {
  router.push(`/ai-optimization?jobId=${encodeURIComponent(props.job.job_id)}`)
}
</script>

<style scoped>
.card.clickable { cursor:pointer; }
.thumb { aspect-ratio:16/9; width:100%; object-fit:cover; display:block; background:#0a0d16; }
.status-badge { position:absolute; top:10px; right:10px; padding:4px 10px; border-radius:999px; font-size:11px; font-weight:700; }
.status-badge.pending   { background:rgba(253,230,138,.15); color:var(--warning); border:1px solid rgba(253,230,138,.3); }
.status-badge.running   { background:rgba(147,197,253,.15); color:var(--running); border:1px solid rgba(147,197,253,.3); }
.status-badge.stitching { background:rgba(192,132,252,.15); color:var(--accent-2); border:1px solid rgba(192,132,252,.3); }
.status-badge.completed { background:rgba(134,239,172,.15); color:var(--success); border:1px solid rgba(134,239,172,.3); }
.status-badge.failed    { background:rgba(252,165,165,.15); color:var(--danger); border:1px solid rgba(252,165,165,.3); }
.progress-wrap { height:3px; background:rgba(255,255,255,.06); }
.progress-bar  { height:100%; transition:width .3s; }
.card-body { padding:14px; }
.card-header { display:flex; justify-content:space-between; align-items:center; gap:10px; margin-bottom:10px; }
.card-title { margin:0; font-size:16px; }
.card-footer { padding:0 14px 12px; display:flex; justify-content:space-between; align-items:center; }
.log-line { font-size:11px; color:var(--muted); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:230px; cursor:pointer; }
.action-buttons { display:flex; gap:8px; }
.ai-btn { background:transparent; border:1px solid rgba(147,197,253,.3); color:var(--running); border-radius:8px; padding:4px 10px; font-size:11px; cursor:pointer; }
.ai-btn:hover { background:rgba(147,197,253,.1); }
.delete-btn { background:transparent; border:1px solid rgba(252,165,165,.3); color:var(--danger); border-radius:8px; padding:4px 10px; font-size:11px; cursor:pointer; }
.delete-btn:hover { background:rgba(252,165,165,.1); }
</style>
