<template>
  <div class="results-view">
  <section class="hero">
    <div class="hero-content">
      <div class="hero-eyebrow">CenterPoint Visualizer</div>
      <h1>Visualization Results</h1>
      <p>Click a completed card to play the MP4. Jobs that are still running refresh every 5 seconds.</p>
    </div>
    <div class="stats">
      <div class="stat"><span class="label">Total</span><span class="value">{{ stats.total }}</span></div>
      <div class="stat"><span class="label">Running</span><span class="value" style="color:var(--running)">{{ stats.running }}</span></div>
      <div class="stat"><span class="label">Done</span><span class="value" style="color:var(--result-done)">{{ stats.done }}</span></div>
      <div class="stat"><span class="label">Failed</span><span class="value" style="color:var(--danger)">{{ stats.failed }}</span></div>
    </div>
  </section>

  <section class="controls">
    <div class="search-box">
      <div class="search-icon-wrapper">🔍</div>
      <input v-model="search" type="text" placeholder="Search by clip id or job id">
      <div class="filter-btns">
        <button v-for="s in statusFilters" :key="s" :class="['filter-btn', { active: filterStatus === s }]" @click="filterStatus = s">
          {{ s === 'all' ? 'All' : fmtStatus(s) }}
        </button>
      </div>
    </div>
    <button class="btn-secondary btn-refresh" @click="load()">
      <span :class="['refresh-icon', { spinning: loading }]">🔄</span>
      Refresh
    </button>
  </section>

  <div v-if="loading" class="loading">
    <div class="spinner"></div>
    <div class="loading-text">Loading jobs…</div>
  </div>
  <div v-else-if="!filtered.length" class="empty">
    <div class="empty-icon">📋</div>
    <div class="empty-message">{{ filterStatus === 'all' ? 'No jobs yet. Go to Clips, pick clips, and submit a visualization job.' : 'No matching jobs.' }}</div>
  </div>
  <div v-else class="grid">
    <JobCard
      v-for="j in filtered" :key="j.job_id"
      :job="j"
      @play-video="openVideo"
      @show-log="openLog"
      @delete="doDelete"
    />
  </div>

  <VideoModal :visible="videoOpen" :job="videoJob" @close="videoOpen = false" />
  <LogModal :visible="logOpen" :job="logJob" @close="logOpen = false" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { fetchJobs, deleteJob } from '../api.js'
import { fmtStatus } from '../utils.js'
import JobCard from '../components/JobCard.vue'
import VideoModal from '../components/VideoModal.vue'
import LogModal from '../components/LogModal.vue'

const statusFilters = ['all', 'pending', 'running', 'completed', 'failed']

const allJobs = ref([])
const loading = ref(true)
const search = ref('')
const filterStatus = ref('all')
const videoOpen = ref(false)
const videoJob = ref(null)
const logOpen = ref(false)
const logJob = ref(null)
let refreshTimer = null
let searchTimer = null

const stats = computed(() => ({
  total: allJobs.value.length || '—',
  running: allJobs.value.filter(j => j.status === 'running' || j.status === 'stitching').length,
  done: allJobs.value.filter(j => j.status === 'completed').length,
  failed: allJobs.value.filter(j => j.status === 'failed').length,
}))

const filtered = computed(() => {
  let result = [...allJobs.value]
  const q = search.value.trim().toLowerCase()
  if (q) result = result.filter(j => j.clip_id.includes(q) || j.job_id.includes(q))
  if (filterStatus.value !== 'all') result = result.filter(j => j.status === filterStatus.value)
  return result
})

function scheduleRefresh() {
  if (refreshTimer) clearTimeout(refreshTimer)
  const hasActive = allJobs.value.some(j => ['running', 'stitching', 'pending'].includes(j.status))
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

function openVideo(job) { videoJob.value = job; videoOpen.value = true }
function openLog(job) { logJob.value = job; logOpen.value = true }

async function doDelete(jobId) {
  if (!confirm('Delete this job and its outputs?')) return
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

watch(search, (newVal) => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    // 搜索逻辑已在computed属性中处理
  }, 300)
})

onMounted(() => {
  load()
  window.addEventListener('keydown', onKeydown)
})
onUnmounted(() => {
  if (refreshTimer) clearTimeout(refreshTimer)
  if (searchTimer) clearTimeout(searchTimer)
  window.removeEventListener('keydown', onKeydown)
})
</script>

<style scoped>
/* Results-only: bright yellow for completed / “success” (inherits into JobCard) */
.results-view {
  --result-done: #fff176;
  --result-done-bg: rgba(255, 241, 118, 0.2);
  --result-done-border: rgba(255, 245, 150, 0.45);
}

:root[data-theme='light'] .results-view {
  --result-done: #ca8a04;
  --result-done-bg: rgba(202, 138, 4, 0.14);
  --result-done-border: rgba(202, 138, 4, 0.32);
}

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

.refresh-icon {
  font-size: 14px;
}

.refresh-icon.spinning {
  animation: spin 2s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.loading-text {
  color: var(--muted);
  font-size: 14px;
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 20px;
}

@media (max-width: 768px) {
  .hero {
    flex-direction: column;
    align-items: flex-start;
    gap: 16px;
  }
  
  .stats {
    width: 100%;
    justify-content: space-between;
  }
  
  .controls {
    flex-direction: column;
    align-items: stretch;
  }
  
  .filter-btns {
    justify-content: center;
  }
  
  .grid {
    grid-template-columns: 1fr;
  }
}
</style>