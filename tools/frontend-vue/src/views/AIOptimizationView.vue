<template>
  <section class="hero hero-ai">
    <div class="hero-copy">
      <div class="hero-eyebrow">CenterPoint Intelligence</div>
      <h1>AI Optimization Studio</h1>
      <p>针对指定 job 提交问题描述，沉淀可追溯的优化建议。你可以把一次调参尝试、失败原因和 AI 建议留在同一个工作流里。</p>
    </div>

    <div class="stats stats-ai">
      <div class="stat">
        <span class="label">Requests</span>
        <span class="value">{{ stats.total }}</span>
      </div>
      <div class="stat">
        <span class="label">Unique Jobs</span>
        <span class="value">{{ stats.uniqueJobs }}</span>
      </div>
      <div class="stat">
        <span class="label">Latest</span>
        <span class="value value-small">{{ stats.latest }}</span>
      </div>
    </div>
  </section>

  <section class="controls controls-ai">
    <div class="search-box search-box-ai">
      <span>Filter</span>
      <input v-model="search" type="text" placeholder="按 job id 或问题描述搜索">
      <span v-if="search" class="badge search-count">{{ filteredOptimizations.length }} results</span>
    </div>

    <div class="control-actions">
      <button class="btn-secondary btn-refresh" type="button" @click="loadOptimizations">刷新列表</button>
      <button class="btn-secondary btn-refresh" type="button" @click="resetForm">清空表单</button>
    </div>
  </section>

  <section class="ai-layout">
    <article class="card compose-card">
      <div class="compose-head">
        <div>
          <div class="section-kicker">Submit Request</div>
          <h2>提交新的优化请求</h2>
        </div>
        <span class="badge compose-badge">{{ form.jobId ? 'Job linked' : 'Awaiting job id' }}</span>
      </div>

      <div class="compose-grid">
        <div class="field">
          <label for="jobId">作业 ID</label>
          <input id="jobId" v-model.trim="form.jobId" type="text" placeholder="例如 job_20260413_001">
        </div>

        <div class="field field-note">
          <label>当前状态</label>
          <div class="field-note__content">
            <span class="note-pill">{{ isSubmitting ? '提交中' : '可提交' }}</span>
            <span class="note-text">建议结合 Results 页里的失败日志、参数或现象来描述问题。</span>
          </div>
        </div>
      </div>

      <div class="field field-textarea">
        <label for="description">问题描述</label>
        <textarea
          id="description"
          v-model.trim="form.description"
          placeholder="例如：车辆框有明显偏移、远距离漏检较多、同一路段结果抖动明显……"
        ></textarea>
      </div>

      <div class="compose-actions">
        <button class="btn-primary" type="button" :disabled="isSubmitting" @click="submitRequest">
          {{ isSubmitting ? '提交中...' : '生成优化建议' }}
        </button>
        <p class="compose-tip">提交后会自动刷新建议列表，并在右侧保留本次最新响应。</p>
      </div>
    </article>

    <article class="card response-card">
      <div class="compose-head">
        <div>
          <div class="section-kicker">Latest Response</div>
          <h2>最新 AI 建议</h2>
        </div>
        <span class="badge compose-badge">{{ response ? 'Ready' : 'Waiting' }}</span>
      </div>

      <div v-if="response" class="response-panel">
        <pre>{{ response }}</pre>
      </div>
      <div v-else class="response-empty">
        提交一个 job 后，AI 返回的建议会先展示在这里，方便你边看边调整页面、参数或结果。
      </div>
    </article>
  </section>

  <div v-if="loadingOptimizations" class="loading">Loading optimizations…</div>
  <div v-else-if="!filteredOptimizations.length" class="empty">
    还没有优化建议。你可以从 Results 页点击 “AI优化”，或者直接在这里输入 job id 提交请求。
  </div>
  <div v-else class="grid ai-grid">
    <article v-for="opt in filteredOptimizations" :key="opt.id" class="card optimization-card">
      <div class="optimization-top">
        <div>
          <div class="section-kicker">Job</div>
          <h2 class="optimization-title">{{ opt.jobId }}</h2>
        </div>
        <div class="optimization-actions">
          <span class="badge timestamp-badge">{{ formatDate(opt.createdAt) }}</span>
          <button class="delete-btn" type="button" @click="removeOptimization(opt.id)">删除</button>
        </div>
      </div>

      <div class="meta optimization-meta">
        <div class="meta-item">
          <span class="label">Request</span>
          <span class="value">{{ summarizeText(opt.description || '无描述') }}</span>
        </div>
        <div class="meta-item">
          <span class="label">Response Size</span>
          <span class="value">{{ responseLength(opt.response) }}</span>
        </div>
      </div>

      <div class="optimization-block">
        <div class="block-label">问题描述</div>
        <p class="optimization-text">{{ opt.description || '无' }}</p>
      </div>

      <div class="optimization-block">
        <div class="block-header">
          <span class="block-label">优化建议</span>
          <button class="toggle-btn" type="button" @click="toggleExpand(opt.id)">
            {{ expandedOptimizations[opt.id] ? '收起' : '展开全文' }}
          </button>
        </div>

        <div :class="['response-content', { expanded: expandedOptimizations[opt.id] }]">
          <pre>{{ opt.response }}</pre>
        </div>
      </div>
    </article>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { deleteAIOptimization, fetchAIOptimizations, submitAIOptimization } from '../api.js'

const form = reactive({
  jobId: '',
  description: '',
})
const isSubmitting = ref(false)
const response = ref('')
const allOptimizations = ref([])
const loadingOptimizations = ref(false)
const search = ref('')
const expandedOptimizations = reactive({})

const stats = computed(() => {
  const total = allOptimizations.value.length
  const uniqueJobs = new Set(allOptimizations.value.map((opt) => opt.jobId).filter(Boolean)).size
  const latestItem = allOptimizations.value[0]
  return {
    total: total || '—',
    uniqueJobs: uniqueJobs || '—',
    latest: latestItem ? formatDate(latestItem.createdAt) : '—',
  }
})

const filteredOptimizations = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return allOptimizations.value
  return allOptimizations.value.filter((opt) => {
    const jobId = (opt.jobId || '').toLowerCase()
    const description = (opt.description || '').toLowerCase()
    return jobId.includes(q) || description.includes(q)
  })
})

function formatDate(timestamp) {
  if (!timestamp) return '未知时间'
  const numeric = Number(timestamp)
  const value = numeric < 1e12 ? numeric * 1000 : numeric
  return new Date(value).toLocaleString()
}

function summarizeText(text) {
  return text.length > 28 ? `${text.slice(0, 28)}...` : text
}

function responseLength(text) {
  const count = (text || '').trim().length
  return count ? `${count} chars` : '0 chars'
}

function resetForm() {
  form.description = ''
  if (!new URLSearchParams(window.location.search).get('jobId')) {
    form.jobId = ''
  }
}

async function submitRequest() {
  if (!form.jobId) {
    alert('请输入作业 ID')
    return
  }

  isSubmitting.value = true
  response.value = ''
  try {
    const data = await submitAIOptimization(form.jobId, form.description)
    response.value = data.response || ''
    await loadOptimizations()
  } catch (error) {
    alert(`请求失败: ${error.message}`)
  } finally {
    isSubmitting.value = false
  }
}

async function loadOptimizations() {
  loadingOptimizations.value = true
  try {
    const data = await fetchAIOptimizations()
    allOptimizations.value = (data.optimizations || []).slice().sort((a, b) => Number(b.createdAt || 0) - Number(a.createdAt || 0))
  } catch (error) {
    console.error('加载优化建议失败:', error)
  } finally {
    loadingOptimizations.value = false
  }
}

async function removeOptimization(id) {
  if (!confirm('确定要删除这条优化建议吗？')) return
  try {
    await deleteAIOptimization(id)
    await loadOptimizations()
  } catch (error) {
    alert(`删除失败: ${error.message}`)
  }
}

function toggleExpand(id) {
  expandedOptimizations[id] = !expandedOptimizations[id]
}

onMounted(() => {
  const urlParams = new URLSearchParams(window.location.search)
  const jobId = urlParams.get('jobId')
  if (jobId) {
    form.jobId = jobId
  }
  loadOptimizations()
})
</script>

<style scoped>
.hero-ai {
  position: relative;
  overflow: hidden;
}

.hero-ai::before {
  content: '';
  position: absolute;
  inset: 0;
  background:
    radial-gradient(circle at 10% 18%, rgba(125, 211, 252, 0.16), transparent 26%),
    radial-gradient(circle at 84% 20%, rgba(192, 132, 252, 0.14), transparent 30%);
  pointer-events: none;
}

.hero-copy,
.stats-ai {
  position: relative;
  z-index: 1;
}

.hero-copy {
  max-width: 760px;
}

.hero-eyebrow {
  display: inline-flex;
  align-items: center;
  padding: 6px 11px;
  border-radius: 999px;
  margin-bottom: 12px;
  background: rgba(125, 211, 252, 0.10);
  border: 1px solid rgba(125, 211, 252, 0.16);
  color: var(--accent);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .14em;
  text-transform: uppercase;
}

.stats-ai {
  max-width: 430px;
}

.value-small {
  font-size: 14px;
  line-height: 1.4;
}

.controls-ai {
  align-items: stretch;
}

.search-box-ai {
  min-height: 64px;
}

.search-count {
  align-self: center;
}

.control-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.btn-refresh {
  min-width: 128px;
}

.ai-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(320px, 0.95fr);
  gap: 18px;
  margin-bottom: 20px;
}

.compose-card,
.response-card,
.optimization-card {
  padding: 22px;
}

.compose-head,
.optimization-top {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 18px;
}

.compose-head h2,
.optimization-title {
  margin: 4px 0 0;
  font-size: 22px;
}

.section-kicker {
  color: var(--muted);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: .12em;
  font-weight: 700;
}

.compose-badge,
.timestamp-badge {
  margin-top: 4px;
}

.compose-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(220px, .8fr);
  gap: 14px;
  margin-bottom: 14px;
}

.field-textarea {
  margin-bottom: 16px;
}

.field textarea {
  width: 100%;
  min-height: 160px;
  padding: 14px 16px;
  border-radius: 14px;
  border: 1px solid var(--border);
  background: var(--panel-alt);
  color: var(--text);
  font-size: 14px;
  line-height: 1.6;
  resize: vertical;
  transition:
    background .22s var(--ease-out),
    border-color .22s var(--ease-out),
    color .22s var(--ease-out),
    box-shadow .22s var(--ease-out);
}

.field textarea:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(125, 211, 252, 0.12);
}

.field-note__content {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 100%;
  padding: 14px 16px;
  border-radius: 14px;
  border: 1px solid var(--border);
  background: linear-gradient(180deg, rgba(125, 211, 252, 0.07), rgba(192, 132, 252, 0.06));
}

.note-pill {
  align-self: flex-start;
  padding: 5px 10px;
  border-radius: 999px;
  background: rgba(125, 211, 252, 0.14);
  color: var(--accent);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .06em;
  text-transform: uppercase;
}

.note-text {
  color: var(--muted);
  font-size: 13px;
  line-height: 1.6;
}

.compose-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.compose-tip {
  margin: 0;
  color: var(--muted);
  font-size: 13px;
  line-height: 1.6;
  max-width: 420px;
}

.response-panel {
  min-height: 100%;
  border: 1px solid var(--border);
  border-radius: 16px;
  background: linear-gradient(180deg, rgba(125, 211, 252, 0.06), rgba(255, 255, 255, 0.02));
  overflow: hidden;
}

.response-panel pre,
.response-content pre {
  margin: 0;
  padding: 18px;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: inherit;
  font-size: 13px;
  line-height: 1.7;
  color: var(--text);
}

.response-empty {
  min-height: 280px;
  border: 1px dashed var(--border);
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 24px;
  color: var(--muted);
  line-height: 1.7;
  background: rgba(255, 255, 255, 0.03);
}

.ai-grid {
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
}

.optimization-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.optimization-meta {
  margin-bottom: 16px;
}

.optimization-block + .optimization-block {
  margin-top: 16px;
}

.block-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.block-label {
  color: var(--muted);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .12em;
  text-transform: uppercase;
}

.optimization-text {
  margin: 0;
  color: var(--text);
  line-height: 1.7;
  font-size: 14px;
}

.response-content {
  border: 1px solid var(--border);
  border-radius: 14px;
  overflow: hidden;
  max-height: 180px;
  background: rgba(255, 255, 255, 0.03);
  transition: max-height .24s var(--ease-out), border-color .24s var(--ease-out);
}

.response-content.expanded {
  max-height: 1200px;
}

.toggle-btn,
.delete-btn {
  border-radius: 10px;
  cursor: pointer;
  font-size: 12px;
  font-weight: 700;
  transition:
    background .18s var(--ease-out),
    border-color .18s var(--ease-out),
    color .18s var(--ease-out),
    transform .18s var(--ease-out);
}

.toggle-btn {
  padding: 7px 12px;
  border: 1px solid var(--border);
  background: transparent;
  color: var(--muted);
}

.toggle-btn:hover {
  background: var(--nav-hover);
  color: var(--text);
}

.delete-btn {
  padding: 7px 12px;
  border: 1px solid rgba(252, 165, 165, .26);
  background: rgba(252, 165, 165, .08);
  color: var(--danger);
}

.delete-btn:hover {
  background: rgba(252, 165, 165, .14);
  border-color: rgba(252, 165, 165, .4);
}

@media (max-width: 1080px) {
  .ai-layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 900px) {
  .compose-grid {
    grid-template-columns: 1fr;
  }

  .compose-actions,
  .optimization-top,
  .block-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .control-actions {
    width: 100%;
  }

  .btn-refresh {
    flex: 1;
  }
}
</style>
