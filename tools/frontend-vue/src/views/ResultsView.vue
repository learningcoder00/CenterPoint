<template>
  <section class="hero">
    <div class="hero-content">
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
      <span class="search-icon">🔍</span>
      <input v-model="search" type="text" placeholder="Search by clip id or job id">
    </div>
    <div class="filter-btns">
      <button v-for="s in statusFilters" :key="s" :class="['filter-btn', { active: filterStatus === s }]" @click="filterStatus = s">
        {{ s === 'all' ? 'All' : fmtStatus(s) }}
      </button>
    </div>
    <button class="btn-refresh" @click="load()">
      <span class="refresh-icon">🔄</span>
      刷新
    </button>
  </section>

  <div v-if="loading" class="loading-container">
    <div class="loading-spinner"></div>
    <div class="loading-text">Loading jobs…</div>
  </div>
  <div v-else-if="!filtered.length" class="empty">
    <div class="empty-icon">📋</div>
    <div class="empty-message">{{ filterStatus === 'all' ? '还没有任务。去 Clips 页面选择 clip 并提交可视化任务。' : '没有匹配的任务。' }}</div>
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
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
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
.hero {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  padding: 24px;
  background: var(--panel);
  border-radius: 16px;
  border: 1px solid var(--border);
  box-shadow: var(--shadow);
}

.hero-content h1 {
  margin: 0 0 8px 0;
  font-size: 24px;
  font-weight: 600;
  color: var(--text);
}

.hero-content p {
  margin: 0;
  font-size: 14px;
  color: var(--text-muted);
}

.stats {
  display: flex;
  gap: 16px;
  align-items: center;
}

.stat {
  text-align: center;
  min-width: 80px;
}

.stat .label {
  display: block;
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 4px;
}

.stat .value {
  display: block;
  font-size: 18px;
  font-weight: 600;
  color: var(--text);
}

.controls {
  display: flex;
  gap: 16px;
  margin-bottom: 24px;
  flex-wrap: wrap;
  align-items: center;
}

.search-box {
  position: relative;
  flex: 1;
  min-width: 200px;
}

.search-icon {
  position: absolute;
  left: 12px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-muted);
  font-size: 14px;
}

.search-box input {
  width: 100%;
  padding: 10px 12px 10px 36px;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: var(--panel);
  color: var(--text);
  font-size: 14px;
  transition: all 0.3s ease;
}

.search-box input:focus {
  outline: none;
  border-color: var(--primary);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.1);
}

.filter-btns {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.filter-btn {
  padding: 8px 16px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--panel);
  color: var(--text);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.3s ease;
  white-space: nowrap;
}

.filter-btn:hover {
  background: rgba(255, 255, 255, 0.08);
}

.filter-btn.active {
  background: var(--primary);
  color: white;
  border-color: var(--primary);
}

.btn-refresh {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 16px;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: var(--panel);
  color: var(--text);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.3s ease;
  white-space: nowrap;
}

.btn-refresh:hover {
  background: rgba(255, 255, 255, 0.08);
  transform: translateY(-1px);
}

.refresh-icon {
  font-size: 14px;
  animation: spin 2s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.loading-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  text-align: center;
}

.loading-spinner {
  width: 40px;
  height: 40px;
  border: 3px solid var(--border);
  border-top: 3px solid var(--primary);
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 16px;
}

.loading-text {
  color: var(--text-muted);
  font-size: 14px;
}

.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  text-align: center;
  background: var(--panel);
  border-radius: 16px;
  border: 1px solid var(--border);
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 16px;
  color: var(--text-muted);
}

.empty-message {
  color: var(--text-muted);
  font-size: 14px;
  line-height: 1.5;
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