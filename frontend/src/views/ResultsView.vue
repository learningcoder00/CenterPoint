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
    <button class="btn-secondary btn-refresh" type="button" :disabled="refreshing" @click="onRefresh">
      <span class="refresh-icon">🔄</span>
      {{ refreshing ? 'Refreshing…' : 'Refresh' }}
    </button>
    <button
      :class="['btn-secondary', 'btn-select-toggle', { active: selectMode }]"
      type="button"
      :title="selectMode ? 'Exit selection mode' : 'Enter multi-select mode to batch delete jobs'"
      @click="toggleSelectMode"
    >
      <span class="refresh-icon">☑</span>
      {{ selectMode ? 'Cancel' : 'Select' }}
    </button>
    <button
      class="btn-secondary btn-export"
      type="button"
      :disabled="!filtered.length"
      :title="filtered.length ? `Download ${filtered.length} job row${filtered.length === 1 ? '' : 's'} as CSV` : 'No jobs to export'"
      @click="exportCsv"
    >
      <span class="refresh-icon">⬇</span>
      Export CSV
    </button>
  </section>

  <section v-if="selectMode" class="bulk-bar">
    <span class="bulk-bar__count">
      <strong>{{ selectedIds.size }}</strong> selected
      <span v-if="staleCount" class="bulk-bar__sub">· {{ staleCount }} stale on this page</span>
    </span>
    <button class="bulk-btn" type="button" :disabled="!filtered.length" @click="selectAllVisible">
      Select all visible ({{ filtered.length }})
    </button>
    <button
      class="bulk-btn"
      type="button"
      :disabled="!staleCount"
      :title="staleCount ? 'Add stale jobs (missing MP4 or clip not in current dataset) to the selection' : 'No stale jobs detected'"
      @click="selectStale"
    >
      Select stale ({{ staleCount }})
    </button>
    <button class="bulk-btn" type="button" :disabled="!selectedIds.size" @click="clearSelection">
      Clear
    </button>
    <button
      class="bulk-btn bulk-btn--danger"
      type="button"
      :disabled="!selectedIds.size || bulkDeleting"
      @click="bulkDeleteSelected"
    >
      <span class="refresh-icon">🗑</span>
      {{ bulkDeleting ? 'Deleting…' : `Delete selected (${selectedIds.size})` }}
    </button>
    <button
      class="bulk-btn bulk-btn--ghost"
      type="button"
      :disabled="bulkDeleting || !standardJobs.length"
      :title="`Wipe every visualization job (${standardJobs.length}) — does not touch A/B compare jobs`"
      @click="bulkDeleteAll"
    >
      <span class="refresh-icon">⚠</span>
      Delete ALL
    </button>
  </section>

  <div v-if="loading" class="loading">
    <div class="spinner"></div>
    <div class="loading-text">Loading jobs…</div>
  </div>
  <div v-else-if="!filtered.length" class="empty">
    <div class="empty-icon">📋</div>
    <div class="empty-message">{{ filterStatus === 'all' ? 'No jobs yet. Go to Clips, pick clips, and submit a visualization job.' : 'No matching jobs.' }}</div>
    <p v-if="filterStatus === 'all' && hasCompareJobs" class="empty-hint">
      Looking for A/B compare jobs? They live on the
      <router-link to="/compare">Compare page</router-link>.
    </p>
  </div>
  <div v-else class="grid">
    <JobCard
      v-for="j in filtered" :key="j.job_id"
      :job="j"
      :show-star-toggle="true"
      :selectable="selectMode"
      :selected="selectedIds.has(j.job_id)"
      @play-video="openVideo"
      @show-log="openLog"
      @delete="doDelete"
      @cancel="doCancel"
      @toggle-star="onToggleStar"
      @toggle-select="onToggleSelect"
    />
  </div>

  <VideoModal :visible="videoOpen" :job="videoJob" @close="videoOpen = false" @review-updated="onReviewUpdated" />
  <LogModal :visible="logOpen" :job="logJob" @close="logOpen = false" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, reactive, watch } from 'vue'
import { fetchJobs, deleteJob, starJob, unstarJob, bulkDeleteJobs, cancelJob } from '../api.js'
import { downloadFile, fmtStatus, fmtTime, toCsv } from '../utils.js'
import JobCard from '../components/JobCard.vue'
import VideoModal from '../components/VideoModal.vue'
import LogModal from '../components/LogModal.vue'

const statusFilters = ['all', 'pending', 'running', 'completed', 'failed', 'cancelled']

const allJobs = ref([])
const loading = ref(true)
const refreshing = ref(false)
const search = ref('')
const filterStatus = ref('all')
const videoOpen = ref(false)
const videoJob = ref(null)
const logOpen = ref(false)
const logJob = ref(null)
const selectMode = ref(false)
const selectedIds = reactive(new Set())
const bulkDeleting = ref(false)
let refreshTimer = null
let searchTimer = null

const standardJobs = computed(() =>
  (allJobs.value || []).filter(j => j.visualization_mode !== 'bev_compare')
)

const hasCompareJobs = computed(() =>
  (allJobs.value || []).some(j => j.visualization_mode === 'bev_compare')
)

const stats = computed(() => ({
  total: standardJobs.value.length || '—',
  running: standardJobs.value.filter(j => j.status === 'running' || j.status === 'stitching').length,
  done: standardJobs.value.filter(j => j.status === 'completed').length,
  failed: standardJobs.value.filter(j => j.status === 'failed').length,
}))

const filtered = computed(() => {
  let result = [...standardJobs.value]
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

function exportCsv() {
  const rows = filtered.value
  if (!rows.length) return
  const header = [
    'job_id', 'clip_id', 'status', 'review_status', 'starred',
    'visualization_mode', 'config', 'checkpoint',
    'progress', 'total', 'frame_count',
    'created_at', 'updated_at', 'mp4_path',
  ]
  const body = rows.map((j) => [
    j.job_id, j.clip_id, j.status, j.review_status, j.starred ? 'yes' : '',
    j.visualization_mode, j.config, j.checkpoint,
    j.progress, j.total, j.frame_count,
    fmtTime(j.created_at), fmtTime(j.updated_at), j.mp4_path,
  ])
  const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')
  const suffix = filterStatus.value === 'all' ? '' : `-${filterStatus.value}`
  downloadFile(toCsv([header, ...body]), `centerpoint-jobs${suffix}-${stamp}.csv`, 'text/csv;charset=utf-8')
}

async function doDelete(jobId) {
  if (!confirm('Delete this job and its outputs?')) return
  try {
    await deleteJob(jobId)
    selectedIds.delete(jobId)
    await load()
  } catch (e) {
    alert(`Delete failed: ${e.message}`)
  }
}

async function doCancel(jobId) {
  const job = allJobs.value.find(j => j.job_id === jobId)
  const msg = job && job.status === 'pending'
    ? 'Remove this pending job from the queue?'
    : 'Stop this running inference? Partial frames will be cleaned up.'
  if (!confirm(msg)) return
  try {
    await cancelJob(jobId)
    await load()
  } catch (e) {
    alert(`Cancel failed: ${e.message}`)
  }
}

const staleCount = computed(() => filtered.value.filter(j => j.stale).length)

function toggleSelectMode() {
  selectMode.value = !selectMode.value
  if (!selectMode.value) selectedIds.clear()
}

function onToggleSelect(jobId) {
  if (selectedIds.has(jobId)) selectedIds.delete(jobId)
  else selectedIds.add(jobId)
}

function selectAllVisible() {
  filtered.value.forEach(j => selectedIds.add(j.job_id))
}

function selectStale() {
  filtered.value.filter(j => j.stale).forEach(j => selectedIds.add(j.job_id))
}

function clearSelection() {
  selectedIds.clear()
}

async function bulkDeleteSelected() {
  if (!selectedIds.size) return
  const ids = [...selectedIds]
  if (!confirm(`Delete ${ids.length} job${ids.length === 1 ? '' : 's'} and their outputs? This cannot be undone.`)) {
    return
  }
  bulkDeleting.value = true
  try {
    const res = await bulkDeleteJobs({ jobIds: ids })
    selectedIds.clear()
    await load(true)
    const summary = [
      `Deleted ${res.deleted}`,
      res.not_found ? `not found ${res.not_found}` : null,
      res.failed ? `failed ${res.failed}` : null,
    ].filter(Boolean).join(' · ')
    if (res.failed && res.errors?.length) {
      alert(`${summary}\n\nFirst errors:\n` + res.errors.slice(0, 3).join('\n'))
    }
  } catch (e) {
    alert(`Bulk delete failed: ${e.message}`)
  } finally {
    bulkDeleting.value = false
  }
}

async function bulkDeleteAll() {
  if (!standardJobs.value.length) return
  const ids = standardJobs.value.map(j => j.job_id)
  if (!confirm(
    `Delete ALL ${ids.length} visualization job${ids.length === 1 ? '' : 's'} and their outputs?\n\n` +
    `This will not touch A/B compare jobs (manage them on the Compare page).`,
  )) {
    return
  }
  bulkDeleting.value = true
  try {
    const res = await bulkDeleteJobs({ jobIds: ids })
    selectedIds.clear()
    selectMode.value = false
    await load()
    if (res.failed && res.errors?.length) {
      alert(`Deleted ${res.deleted}, ${res.failed} failed.\n\nFirst errors:\n` + res.errors.slice(0, 3).join('\n'))
    }
  } catch (e) {
    alert(`Bulk delete failed: ${e.message}`)
  } finally {
    bulkDeleting.value = false
  }
}

// Drop selected ids that no longer exist after a refresh (e.g. server-side cleanup
// or dataset switch); keeps the toolbar counter honest.
watch(allJobs, (jobs) => {
  if (!selectedIds.size) return
  const known = new Set(jobs.map(j => j.job_id))
  for (const id of [...selectedIds]) if (!known.has(id)) selectedIds.delete(id)
})

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

.btn-refresh,
.btn-export {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  align-self: stretch;
}

.btn-export:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.btn-select-toggle {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  align-self: stretch;
}

.btn-select-toggle.active {
  background: linear-gradient(180deg, rgba(125, 211, 252, 0.28), rgba(125, 211, 252, 0.14));
  border-color: var(--accent);
  color: var(--accent);
}

.bulk-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin-bottom: 22px;
  padding: 12px 16px;
  border: 1px solid var(--border);
  border-radius: 14px;
  background:
    radial-gradient(360px 100px at 0% 50%, color-mix(in srgb, var(--accent) 14%, transparent), transparent 70%),
    var(--panel-alt, rgba(15, 23, 42, 0.45));
  box-shadow: var(--shadow);
}

.bulk-bar__count {
  font-size: 13px;
  font-weight: 700;
  color: var(--muted);
  margin-right: 6px;
}

.bulk-bar__count strong {
  color: var(--accent);
  font-size: 16px;
  margin-right: 4px;
}

.bulk-bar__sub {
  margin-left: 8px;
  font-weight: 600;
  color: #fbbf24;
}

.bulk-btn {
  padding: 8px 14px;
  font-size: 12.5px;
  font-weight: 700;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: var(--panel);
  color: var(--text);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  transition: background .18s var(--ease-out), border-color .18s var(--ease-out), transform .18s var(--ease-out);
}

.bulk-btn:hover:not(:disabled) {
  background: var(--panel-alt);
  border-color: var(--accent);
  transform: translateY(-1px);
}

.bulk-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.bulk-btn--danger {
  background: linear-gradient(180deg, rgba(248, 113, 113, 0.22), rgba(239, 68, 68, 0.10));
  border-color: rgba(248, 113, 113, 0.55);
  color: #fecaca;
}

.bulk-btn--danger:hover:not(:disabled) {
  background: linear-gradient(180deg, rgba(248, 113, 113, 0.32), rgba(239, 68, 68, 0.16));
  border-color: rgba(248, 113, 113, 0.85);
  color: #fee2e2;
}

.bulk-btn--ghost {
  border-style: dashed;
  color: #fbbf24;
  border-color: rgba(251, 191, 36, 0.5);
}

.bulk-btn--ghost:hover:not(:disabled) {
  border-color: rgba(251, 191, 36, 0.85);
  background: rgba(251, 191, 36, 0.12);
  color: #fde68a;
}

.refresh-icon {
  font-size: 14px;
}

.loading-text {
  color: var(--muted);
  font-size: 14px;
}

.empty-hint {
  margin-top: 10px;
  font-size: 13px;
  color: var(--muted);
}
.empty-hint a {
  color: var(--accent);
  text-decoration: none;
  font-weight: 700;
}
.empty-hint a:hover { text-decoration: underline; }

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