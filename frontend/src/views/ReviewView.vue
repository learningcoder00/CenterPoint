<template>
  <div class="review-view">
    <section class="hero">
      <div class="hero-content">
        <div class="hero-eyebrow">CenterPoint Visualizer</div>
        <h1>Review</h1>
        <p>Browse completed visualization jobs by human verdict. Star jobs to keep them on your shortlist.</p>
      </div>
      <div class="stats">
        <div class="stat"><span class="label">Issues</span><span class="value issue">{{ stats.issues }}</span></div>
        <div class="stat"><span class="label">Clean</span><span class="value clean">{{ stats.clean }}</span></div>
        <div class="stat"><span class="label">Pending</span><span class="value pending">{{ stats.pending }}</span></div>
        <div class="stat"><span class="label">Starred jobs</span><span class="value star">{{ stats.starredJobs }}</span></div>
      </div>
    </section>

    <section class="tabs" role="tablist" aria-label="Review filter">
      <button
        v-for="t in tabDefs"
        :key="t.id"
        type="button"
        role="tab"
        :aria-selected="activeTab === t.id"
        :class="['tab-btn', `tab-${t.id}`, { active: activeTab === t.id }]"
        @click="setTab(t.id)"
      >
        <span class="tab-icon" aria-hidden="true">{{ t.icon }}</span>
        <span class="tab-label">{{ t.label }}</span>
        <span class="tab-count">{{ tabCounts[t.id] }}</span>
      </button>
    </section>

    <section class="controls">
      <div class="search-box">
        <div class="search-icon-wrapper">🔍</div>
        <input v-model="search" type="text" placeholder="Search by clip id or job id">
      </div>
      <button class="btn-secondary btn-refresh" type="button" :disabled="refreshing" @click="onRefresh">
        <span class="refresh-icon">🔄</span>
        {{ refreshing ? 'Refreshing…' : 'Refresh' }}
      </button>
    </section>

    <div v-if="loading" class="loading">
      <div class="spinner"></div>
      <div class="loading-text">Loading jobs…</div>
    </div>
    <div v-else-if="!filtered.length" class="empty">
      <div class="empty-icon">📋</div>
      <div class="empty-message">{{ emptyMessage }}</div>
    </div>
    <div v-else class="grid">
      <JobCard
        v-for="j in filtered"
        :key="j.job_id"
        :job="j"
        :show-review="true"
        :show-star-toggle="true"
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
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { fetchJobs, deleteJob, starJob, unstarJob } from '../api.js'
import JobCard from '../components/JobCard.vue'
import VideoModal from '../components/VideoModal.vue'
import LogModal from '../components/LogModal.vue'

const tabDefs = [
  { id: 'issues', label: 'Issues', icon: '⚠' },
  { id: 'clean', label: 'Clean', icon: '✓' },
  { id: 'starred', label: 'Starred', icon: '★' },
  { id: 'all', label: 'All completed', icon: '◆' },
]

const route = useRoute()
const router = useRouter()

const allJobs = ref([])
const loading = ref(true)
const refreshing = ref(false)
const search = ref('')
const activeTab = ref(typeof route.query.tab === 'string' ? route.query.tab : 'issues')
const videoOpen = ref(false)
const videoJob = ref(null)
const logOpen = ref(false)
const logJob = ref(null)
let refreshTimer = null

const completed = computed(() => (allJobs.value || [])
  .filter(j => j.status === 'completed' && j.visualization_mode !== 'bev_compare')
)

const stats = computed(() => {
  const list = completed.value
  return {
    issues: list.filter(j => j.review_status === 'has_issue').length,
    clean: list.filter(j => j.review_status === 'no_issue').length,
    pending: list.filter(j => !j.review_status || j.review_status === 'unreviewed').length,
    starredJobs: list.filter(j => j.starred).length,
  }
})

const tabCounts = computed(() => ({
  issues: stats.value.issues,
  clean: stats.value.clean,
  starred: stats.value.starredJobs,
  all: completed.value.length,
}))

const filtered = computed(() => {
  let list = [...completed.value]
  if (activeTab.value === 'issues') list = list.filter(j => j.review_status === 'has_issue')
  else if (activeTab.value === 'clean') list = list.filter(j => j.review_status === 'no_issue')
  else if (activeTab.value === 'starred') list = list.filter(j => j.starred)
  const q = search.value.trim().toLowerCase()
  if (q) {
    list = list.filter(j =>
      (j.clip_id && j.clip_id.toLowerCase().includes(q)) ||
      (j.job_id && j.job_id.toLowerCase().includes(q))
    )
  }
  return list
})

const emptyMessage = computed(() => {
  if (activeTab.value === 'issues') return 'No jobs marked as issue yet. Open a video and use Review verdict.'
  if (activeTab.value === 'clean') return 'No jobs marked clean yet.'
  if (activeTab.value === 'starred') return 'No starred jobs yet. Star jobs from Review or Results.'
  return 'No completed jobs yet.'
})

function setTab(id) {
  activeTab.value = id
  router.replace({ query: { ...route.query, tab: id } })
}

watch(
  () => route.query.tab,
  (t) => {
    if (typeof t === 'string' && tabDefs.some(x => x.id === t)) activeTab.value = t
  }
)

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

function openVideo(job) {
  videoJob.value = job
  videoOpen.value = true
}

function openLog(job) {
  logJob.value = job
  logOpen.value = true
}

function onReviewUpdated({ jobId, reviewStatus, reviewerNote }) {
  for (const j of allJobs.value) {
    if (j.job_id === jobId) {
      j.review_status = reviewStatus
      if (reviewerNote !== undefined) j.reviewer_note = reviewerNote
    }
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
  } catch (e) {
    alert(`Star update failed: ${e.message}`)
  }
}

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

onMounted(() => {
  if (!tabDefs.some(t => t.id === activeTab.value)) activeTab.value = 'issues'
  load()
  window.addEventListener('keydown', onKeydown)
})

onUnmounted(() => {
  if (refreshTimer) clearTimeout(refreshTimer)
  window.removeEventListener('keydown', onKeydown)
})
</script>

<style scoped>
.review-view {
  --review-issue: #f87171;
  --review-clean: #4ade80;
  --review-pending: #94a3b8;
  --review-star: #fde047;
}

.hero {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 20px;
}

.hero-content h1 {
  margin: 0.2em 0 0.35em;
}

.tabs {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 4px;
  padding: 5px;
  margin-bottom: 20px;
  border: 1px solid var(--border);
  border-radius: 16px;
  background: var(--stat-bg);
  box-shadow: var(--shadow);
  backdrop-filter: blur(10px);
}

.tab-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 9px 16px 9px 14px;
  border-radius: 12px;
  border: 0;
  background: transparent;
  color: var(--muted);
  font-weight: 600;
  font-size: 13px;
  cursor: pointer;
  transition:
    background .2s var(--ease-out),
    color .2s var(--ease-out),
    transform .2s var(--ease-out);
}

.tab-btn:hover:not(.active) {
  color: var(--text);
  background: var(--nav-hover);
}

.tab-btn .tab-icon {
  font-size: 13px;
  line-height: 1;
  opacity: .9;
}

.tab-btn .tab-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 22px;
  height: 20px;
  padding: 0 7px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--muted) 18%, transparent);
  color: color-mix(in srgb, var(--muted) 90%, var(--text));
  font-size: 11px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  transition: background .2s var(--ease-out), color .2s var(--ease-out);
}

.tab-btn.active {
  color: var(--text);
  background: linear-gradient(180deg,
    color-mix(in srgb, var(--accent) 22%, transparent),
    color-mix(in srgb, var(--accent) 12%, transparent));
  box-shadow:
    inset 0 1px 0 color-mix(in srgb, #ffffff 14%, transparent),
    0 8px 18px color-mix(in srgb, var(--accent) 18%, transparent);
}

.tab-btn.tab-issues.active { color: var(--review-issue); }
.tab-btn.tab-issues.active {
  background: linear-gradient(180deg,
    color-mix(in srgb, var(--review-issue) 22%, transparent),
    color-mix(in srgb, var(--review-issue) 10%, transparent));
  box-shadow:
    inset 0 1px 0 color-mix(in srgb, #ffffff 14%, transparent),
    0 8px 18px color-mix(in srgb, var(--review-issue) 18%, transparent);
}
.tab-btn.tab-clean.active { color: var(--review-clean); }
.tab-btn.tab-clean.active {
  background: linear-gradient(180deg,
    color-mix(in srgb, var(--review-clean) 22%, transparent),
    color-mix(in srgb, var(--review-clean) 10%, transparent));
  box-shadow:
    inset 0 1px 0 color-mix(in srgb, #ffffff 14%, transparent),
    0 8px 18px color-mix(in srgb, var(--review-clean) 18%, transparent);
}
.tab-btn.tab-starred.active { color: var(--review-star); }
.tab-btn.tab-starred.active {
  background: linear-gradient(180deg,
    color-mix(in srgb, var(--review-star) 24%, transparent),
    color-mix(in srgb, var(--review-star) 10%, transparent));
  box-shadow:
    inset 0 1px 0 color-mix(in srgb, #ffffff 16%, transparent),
    0 8px 18px color-mix(in srgb, var(--review-star) 22%, transparent);
}

.tab-btn.active .tab-count {
  background: color-mix(in srgb, currentColor 18%, transparent);
  color: currentColor;
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
}

.stats .value.issue { color: var(--review-issue); }
.stats .value.clean { color: var(--review-clean); }
.stats .value.pending { color: var(--review-pending); }
.stats .value.star { color: var(--review-star); }

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 20px;
}

@media (max-width: 768px) {
  .hero { flex-direction: column; }
  .grid { grid-template-columns: 1fr; }
}
</style>
