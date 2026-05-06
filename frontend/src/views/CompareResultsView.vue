<template>
  <div class="compare-view">
    <section class="hero">
      <div class="hero-content">
        <div class="hero-eyebrow">CenterPoint Visualizer</div>
        <h1>
          BEV Compare
          <span class="hero-tag">
            <span class="hero-tag__a">A</span>
            <span class="hero-tag__sep">⇆</span>
            <span class="hero-tag__b">B</span>
          </span>
        </h1>
        <p>Side-by-side BEV jobs that compare two configs/checkpoints on the same clip. Cards refresh every 5 seconds while jobs are running.</p>
      </div>
      <div class="stats">
        <div class="stat"><span class="label">Total</span><span class="value">{{ stats.total }}</span></div>
        <div class="stat"><span class="label">Running</span><span class="value" style="color:var(--running)">{{ stats.running }}</span></div>
        <div class="stat"><span class="label">Done</span><span class="value done">{{ stats.done }}</span></div>
        <div class="stat"><span class="label">Failed</span><span class="value" style="color:var(--danger)">{{ stats.failed }}</span></div>
      </div>
    </section>

    <section class="controls">
      <div class="search-box">
        <div class="search-icon-wrapper">🔍</div>
        <input v-model="search" type="text" placeholder="Search by clip id, job id, or config path">
        <div class="filter-btns">
          <button v-for="s in statusFilters" :key="s" :class="['filter-btn', { active: filterStatus === s }]" @click="filterStatus = s">
            {{ s === 'all' ? 'All' : fmtStatus(s) }}
          </button>
        </div>
      </div>
      <button class="btn-secondary btn-refresh" type="button" :disabled="refreshing" @click="onRefresh">
        <span class="refresh-icon">🔄</span>
        {{ refreshing ? 'Refreshing…' : 'Refresh' }}
      </button>
      <router-link class="btn-compare-cta" to="/clips" title="Pick clips and submit a new compare job">
        <span class="cta-icon">⇆</span>
        New compare
      </router-link>
    </section>

    <div v-if="loading" class="loading">
      <div class="spinner"></div>
      <div class="loading-text">Loading jobs…</div>
    </div>
    <div v-else-if="!filtered.length" class="empty">
      <div class="empty-icon">⇆</div>
      <div class="empty-message">{{ emptyMessage }}</div>
      <router-link v-if="!compareJobs.length" class="btn-primary empty-cta" to="/clips">Go to Clips</router-link>
    </div>
    <div v-else class="grid">
      <JobCard
        v-for="j in filtered" :key="j.job_id"
        :job="j"
        :show-star-toggle="true"
        :show-review="true"
        @play-video="openVideo"
        @show-log="openLog"
        @delete="doDelete"
        @toggle-star="onToggleStar"
      />
    </div>

    <VideoModal :visible="videoOpen" :job="videoJob" @close="videoOpen = false" @review-updated="onReviewUpdated" />
    <LogModal :visible="logOpen" :job="logJob" @close="logOpen = false" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { fetchJobs, deleteJob, starJob, unstarJob } from '../api.js'
import { fmtStatus } from '../utils.js'
import JobCard from '../components/JobCard.vue'
import VideoModal from '../components/VideoModal.vue'
import LogModal from '../components/LogModal.vue'

const statusFilters = ['all', 'pending', 'running', 'completed', 'failed']

const allJobs = ref([])
const loading = ref(true)
const refreshing = ref(false)
const search = ref('')
const filterStatus = ref('all')
const videoOpen = ref(false)
const videoJob = ref(null)
const logOpen = ref(false)
const logJob = ref(null)
let refreshTimer = null

const compareJobs = computed(() =>
  (allJobs.value || []).filter(j => j.visualization_mode === 'bev_compare')
)

const stats = computed(() => ({
  total: compareJobs.value.length || '—',
  running: compareJobs.value.filter(j => j.status === 'running' || j.status === 'stitching').length,
  done: compareJobs.value.filter(j => j.status === 'completed').length,
  failed: compareJobs.value.filter(j => j.status === 'failed').length,
}))

const filtered = computed(() => {
  let result = [...compareJobs.value]
  const q = search.value.trim().toLowerCase()
  if (q) {
    result = result.filter(j =>
      (j.clip_id || '').toLowerCase().includes(q) ||
      (j.job_id || '').toLowerCase().includes(q) ||
      (j.config || '').toLowerCase().includes(q) ||
      (j.config_b || '').toLowerCase().includes(q) ||
      (j.checkpoint || '').toLowerCase().includes(q) ||
      (j.checkpoint_b || '').toLowerCase().includes(q)
    )
  }
  if (filterStatus.value !== 'all') result = result.filter(j => j.status === filterStatus.value)
  return result
})

const emptyMessage = computed(() => {
  if (!compareJobs.value.length) {
    return 'No compare jobs yet. Go to Clips, pick clips, then click “A/B compare”.'
  }
  return 'No matching compare jobs. Try clearing search or filter.'
})

function scheduleRefresh() {
  if (refreshTimer) clearTimeout(refreshTimer)
  const hasActive = compareJobs.value.some(j => ['running', 'stitching', 'pending'].includes(j.status))
  if (hasActive) refreshTimer = setTimeout(() => load(true), 5000)
}

async function load(silent = false) {
  if (!silent) loading.value = true
  try {
    const data = await fetchJobs()
    allJobs.value = data.jobs || []
    scheduleRefresh()
  } catch { /* empty */ }
  if (!silent) loading.value = false
}

async function onRefresh() {
  if (refreshing.value) return
  refreshing.value = true
  const startedAt = Date.now()
  try {
    await load(true)
  } finally {
    const minVisible = 500
    const elapsed = Date.now() - startedAt
    setTimeout(() => { refreshing.value = false }, Math.max(0, minVisible - elapsed))
  }
}

function openVideo(job) { videoJob.value = job; videoOpen.value = true }
function openLog(job) { logJob.value = job; logOpen.value = true }

function onReviewUpdated({ jobId, reviewStatus }) {
  const idx = allJobs.value.findIndex(j => j.job_id === jobId)
  if (idx !== -1) {
    allJobs.value[idx] = { ...allJobs.value[idx], review_status: reviewStatus }
  }
  if (videoJob.value?.job_id === jobId) {
    videoJob.value = { ...videoJob.value, review_status: reviewStatus }
  }
}

async function onToggleStar(job) {
  const wantStar = !job.starred
  try {
    if (wantStar) await starJob(job.job_id)
    else await unstarJob(job.job_id)
    const idx = allJobs.value.findIndex(j => j.job_id === job.job_id)
    if (idx !== -1) {
      allJobs.value[idx] = { ...allJobs.value[idx], starred: wantStar }
    }
    if (videoJob.value?.job_id === job.job_id) {
      videoJob.value = { ...videoJob.value, starred: wantStar }
    }
  } catch (e) {
    alert(`Star update failed: ${e.message}`)
  }
}

async function doDelete(jobId) {
  if (!confirm('Delete this compare job and its outputs?')) return
  try {
    await deleteJob(jobId)
    await load()
  } catch (e) {
    alert(`Delete failed: ${e.message}`)
  }
}

function onKeydown(e) {
  if (e.key === 'Escape') {
    if (videoOpen.value) videoOpen.value = false
    if (logOpen.value) logOpen.value = false
  }
}

onMounted(() => {
  load()
  window.addEventListener('keydown', onKeydown)
})
onUnmounted(() => {
  if (refreshTimer) clearTimeout(refreshTimer)
  window.removeEventListener('keydown', onKeydown)
})
</script>

<style scoped>
.compare-view {
  --result-done: #fff176;
  --result-done-bg: rgba(255, 241, 118, 0.2);
  --result-done-border: rgba(255, 245, 150, 0.45);
}

:root[data-theme='light'] .compare-view {
  --result-done: #ca8a04;
  --result-done-bg: rgba(202, 138, 4, 0.14);
  --result-done-border: rgba(202, 138, 4, 0.32);
}

.hero h1 {
  display: inline-flex;
  align-items: center;
  gap: 14px;
}

.hero-tag {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border-radius: 999px;
  background: linear-gradient(135deg, rgba(56, 189, 248, 0.18), rgba(244, 114, 182, 0.22));
  border: 1px solid rgba(244, 114, 182, 0.45);
  font-size: 14px;
  font-weight: 800;
  letter-spacing: .04em;
}
.hero-tag__a { color: #38bdf8; }
.hero-tag__b { color: #f472b6; }
.hero-tag__sep { color: var(--muted); font-weight: 600; }

.stats .value.done { color: var(--result-done); }

.controls {
  display: flex;
  gap: 16px;
  margin-bottom: 24px;
  flex-wrap: wrap;
  align-items: center;
}

.btn-refresh {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  align-self: stretch;
}
.refresh-icon { font-size: 14px; }

.btn-compare-cta {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  border-radius: 12px;
  border: 1px solid rgba(244, 114, 182, 0.45);
  background: linear-gradient(135deg, rgba(56, 189, 248, 0.18), rgba(244, 114, 182, 0.22));
  color: #fce7f3;
  font-weight: 700;
  font-size: 13px;
  text-decoration: none;
  cursor: pointer;
  transition: transform .18s var(--ease-out), background .18s var(--ease-out), border-color .18s var(--ease-out);
}
.btn-compare-cta:hover {
  transform: translateY(-1px);
  background: linear-gradient(135deg, rgba(56, 189, 248, 0.28), rgba(244, 114, 182, 0.32));
  border-color: rgba(244, 114, 182, 0.7);
}
.cta-icon {
  font-size: 15px;
  background: linear-gradient(135deg, #38bdf8, #f472b6);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  font-weight: 900;
}

.loading-text {
  color: var(--muted);
  font-size: 14px;
}

.empty-cta {
  margin-top: 14px;
  display: inline-flex;
  align-self: center;
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: 20px;
}

@media (max-width: 768px) {
  .hero { flex-direction: column; align-items: flex-start; gap: 16px; }
  .stats { width: 100%; justify-content: space-between; }
  .controls { flex-direction: column; align-items: stretch; }
  .filter-btns { justify-content: center; }
  .grid { grid-template-columns: 1fr; }
}
</style>
