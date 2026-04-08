<template>
  <section class="hero">
    <div>
      <h1>Visualization Results</h1>
      <p>点击已完成的卡片播放 MP4；running 状态的任务每 5 秒自动刷新。</p>
    </div>
    <div class="stats">
      <div class="stat"><span class="label">Total</span><span class="value">{{ stats.total }}</span></div>
      <div class="stat"><span class="label">Running</span><span class="value" style="color:var(--running)">{{ stats.running }}</span></div>
      <div class="stat"><span class="label">Done</span><span class="value" style="color:var(--success)">{{ stats.done }}</span></div>
      <div class="stat"><span class="label">Failed</span><span class="value" style="color:var(--danger)">{{ stats.failed }}</span></div>
    </div>
  </section>

  <section class="controls">
    <div class="search-box">
      <span>Filter</span>
      <input v-model="search" type="text" placeholder="Search by clip id or job id">
    </div>
    <div class="filter-btns">
      <button v-for="s in statusFilters" :key="s" :class="['filter-btn', { active: filterStatus === s }]" @click="filterStatus = s">
        {{ s === 'all' ? 'All' : fmtStatus(s) }}
      </button>
    </div>
    <button class="btn-refresh" @click="load()">刷新</button>
  </section>

  <div v-if="loading" class="loading">Loading jobs…</div>
  <div v-else-if="!filtered.length" class="empty">
    {{ filterStatus === 'all' ? '还没有任务。去 Clips 页面选择 clip 并提交可视化任务。' : '没有匹配的任务。' }}
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
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { fetchJobs, deleteJob } from '../api.js'
import { fmtStatus } from '../utils.js'
import JobCard from '../components/JobCard.vue'
import VideoModal from '../components/VideoModal.vue'
import LogModal from '../components/LogModal.vue'

const statusFilters = ['all', 'pending', 'running', 'stitching', 'completed', 'failed']

const allJobs = ref([])
const loading = ref(true)
const search = ref('')
const filterStatus = ref('all')
const videoOpen = ref(false)
const videoJob = ref(null)
const logOpen = ref(false)
const logJob = ref(null)
let refreshTimer = null

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
  if (!confirm('确认删除该任务及其产物？')) return
  try {
    await deleteJob(jobId)
    await load()
  } catch (e) {
    alert(`删除失败: ${e.message}`)
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
.btn-refresh { padding:10px 16px; border:1px solid var(--border); border-radius:12px; background:transparent; color:var(--text); font-size:13px; cursor:pointer; white-space:nowrap; }
.btn-refresh:hover { background:rgba(255,255,255,.08); }
</style>
