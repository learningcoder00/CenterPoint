<template>
  <section class="hero">
    <div class="hero-copy">
      <div class="hero-eyebrow">CenterPoint Intelligence</div>
      <h1>AI Optimization</h1>
      <p>Submit job ID and problem description to get AI-generated optimization suggestions.</p>
    </div>

    <div class="stats">
      <div class="stat">
        <span class="label">Requests</span>
        <span class="value">{{ stats.total }}</span>
      </div>
      <div class="stat">
        <span class="label">Unique Clips</span>
        <span class="value">{{ stats.uniqueClips }}</span>
      </div>
    </div>
  </section>

  <section class="controls">
    <div class="search-box">
      <div class="search-icon-wrapper">🔍</div>
      <input v-model="search" type="text" placeholder="Search by job ID, clip ID or description">
    </div>

    <div class="control-actions">
      <button class="btn-secondary" type="button" @click="loadOptimizations">Refresh List</button>
      <button class="btn-secondary" type="button" @click="resetForm">Clear Form</button>
    </div>
  </section>

  <section class="ai-layout">
    <div class="compose-section">
      <article class="card compose-card">
        <div class="compose-head">
          <div>
            <div class="section-kicker">Submit Request</div>
            <h2>New Request</h2>
          </div>
          <span :class="['badge', 'status-badge-pill', { 'linked': form.jobId }]">
            {{ form.jobId ? 'Job Linked' : 'Awaiting Job ID' }}
          </span>
        </div>

        <div class="compose-grid">
          <div class="field">
            <label for="jobId">Job ID</label>
            <div class="input-wrapper">
              <input id="jobId" v-model.trim="form.jobId" type="text" placeholder="e.g. job_20260413_001">
              <span class="input-icon">🆔</span>
            </div>
          </div>

          <div class="field">
            <label>Current Status</label>
            <div class="status-indicator-box">
              <div :class="['status-dot', { 'active': !isSubmitting }]"></div>
              <span class="status-text">{{ isSubmitting ? 'Submitting...' : 'Ready to Submit' }}</span>
            </div>
          </div>
        </div>

        <div class="field field-textarea">
          <label for="description">Problem Description</label>
          <textarea
            id="description"
            v-model.trim="form.description"
            placeholder="Describe the issues or areas for improvement in detail..."
          ></textarea>
        </div>

        <div class="compose-footer">
          <button class="btn-primary submit-btn" type="button" :disabled="isSubmitting" @click="submitRequest">
            <span v-if="isSubmitting" class="spinner-small"></span>
            {{ isSubmitting ? 'Processing...' : 'Generate Suggestions' }}
          </button>
          <p class="compose-tip">AI will analyze your job and provide targeted improvements.</p>
        </div>
      </article>
    </div>

    <div class="response-section">
      <article class="card response-card">
        <div class="compose-head">
          <div>
            <div class="section-kicker">Latest Analysis</div>
            <h2>AI Insights</h2>
          </div>
          <div :class="['response-status', { 'has-data': response }]">
            {{ response ? 'Analysis Ready' : 'Waiting for Input' }}
          </div>
        </div>

        <div v-if="response" class="response-container">
          <div class="response-header-bar">
            <span class="response-icon">✨</span>
            <span class="response-label">AI Generated Suggestions</span>
          </div>
          <div class="response-panel markdown-body" v-html="renderMarkdownHtml(response)"></div>
        </div>
        <div v-else class="response-empty">
          <div class="empty-visual">
            <div class="pulse-circle"></div>
            <div class="ai-icon-large">🤖</div>
          </div>
          <p>Submit a request on the left to see AI-generated optimization insights here.</p>
        </div>
      </article>
    </div>
  </section>

  <div class="section-divider">
    <span class="divider-text">Optimization History</span>
  </div>

  <div v-if="loadingOptimizations" class="loading">
    <div class="spinner"></div>
    <div class="loading-text">Loading optimizations…</div>
  </div>
  <div v-else-if="!filteredOptimizations.length" class="empty">
    <div class="empty-icon">💡</div>
    <div class="empty-message">No optimization history found. Start by submitting a new request above.</div>
  </div>
  <div v-else class="grid ai-grid">
    <article v-for="opt in filteredOptimizations" :key="opt.id" class="card optimization-card">
      <div class="optimization-top">
        <div class="opt-id-block">
          <div class="section-kicker">Job ID</div>
          <h2 class="optimization-title" :title="getJobId(opt) || 'Unknown Job'">{{ getJobId(opt) || 'Unknown Job' }}</h2>
          <span class="badge timestamp-badge">{{ formatDate(getCreatedAt(opt)) }}</span>
        </div>
        <div class="optimization-actions">
          <button class="delete-icon-btn" type="button" @click="removeOptimization(opt.id)" title="Delete">
            🗑️
          </button>
        </div>
      </div>

      <div class="meta optimization-meta">
        <div class="meta-item">
          <span class="label">Clip ID</span>
          <span class="value">{{ getClipId(opt) || 'Unknown clip' }}</span>
        </div>
        <div class="meta-item">
          <span class="label">Response Length</span>
          <span class="value">{{ responseLength(opt.response) }}</span>
        </div>
      </div>

      <div class="optimization-block request-block">
        <div class="block-label">User Request</div>
        <p class="optimization-text">{{ opt.description || 'N/A' }}</p>
      </div>

      <div class="optimization-block suggestions-block">
        <div class="block-header">
          <span class="block-label">AI Suggestions</span>
          <span class="scroll-hint">Scroll to read more</span>
        </div>

        <div
          class="response-content-modern markdown-body"
          v-html="renderMarkdownHtml(opt.response)"
        ></div>
      </div>
    </article>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { deleteAIOptimization, fetchAIOptimizations, submitAIOptimization } from '../api.js'
import { renderMarkdownHtml } from '../markdown.js'

const form = reactive({
  jobId: '',
  description: '',
})
const isSubmitting = ref(false)
const response = ref('')
const allOptimizations = ref([])
const loadingOptimizations = ref(false)
const search = ref('')

const stats = computed(() => {
  const total = allOptimizations.value.length
  const uniqueClips = new Set(allOptimizations.value.map((opt) => getClipId(opt)).filter(Boolean)).size
  return {
    total: total || '—',
    uniqueClips: uniqueClips || '—',
  }
})

function getJobId(opt) {
  return opt?.jobId ?? opt?.job_id ?? ''
}

function getClipId(opt) {
  return opt?.clipId ?? opt?.clip_id ?? ''
}

function getCreatedAt(opt) {
  return opt?.createdAt ?? opt?.created_at
}

const filteredOptimizations = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return allOptimizations.value
  return allOptimizations.value.filter((opt) => {
    const jobId = getJobId(opt).toLowerCase()
    const clipId = getClipId(opt).toLowerCase()
    const description = (opt.description || '').toLowerCase()
    return jobId.includes(q) || clipId.includes(q) || description.includes(q)
  })
})

function formatDate(timestamp) {
  if (!timestamp) return 'Unknown Time'
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
    alert('Please enter Job ID')
    return
  }

  isSubmitting.value = true
  response.value = ''
  try {
    const data = await submitAIOptimization(form.jobId, form.description)
    response.value = data.response || ''
    await loadOptimizations()
  } catch (error) {
    console.error('Request failed:', error)
    alert(`Request failed: ${error.message}`)
  } finally {
    isSubmitting.value = false
  }
}

async function loadOptimizations() {
  loadingOptimizations.value = true
  try {
    const data = await fetchAIOptimizations()
    allOptimizations.value = (data.optimizations || []).slice().sort(
      (a, b) => Number(getCreatedAt(b) || 0) - Number(getCreatedAt(a) || 0)
    )
  } catch (error) {
    console.error('Failed to load optimizations:', error)
  } finally {
    loadingOptimizations.value = false
  }
}

async function removeOptimization(id) {
  if (!confirm('Are you sure you want to delete this optimization suggestion?')) return
  try {
    await deleteAIOptimization(id)
    await loadOptimizations()
  } catch (error) {
    console.error('Delete failed:', error)
    alert(`Delete failed: ${error.message}`)
  }
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
.controls {
  display: flex;
  gap: 16px;
  margin-bottom: 32px;
  flex-wrap: wrap;
  align-items: center;
}

.control-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.ai-layout {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
  margin-bottom: 40px;
  align-items: stretch;
}

.compose-card,
.response-card {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 28px;
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 24px;
}

.compose-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 24px;
}

.compose-head h2 {
  margin: 6px 0 0;
  font-size: 24px;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.section-kicker {
  color: var(--accent);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: .15em;
  font-weight: 800;
}

.status-badge-pill {
  padding: 6px 12px;
  border-radius: 10px;
  font-size: 11px;
  background: rgba(255, 255, 255, 0.05);
  color: var(--muted);
  border: 1px solid var(--border);
  transition: all 0.3s ease;
}

.status-badge-pill.linked {
  background: rgba(134, 239, 172, 0.1);
  color: var(--success);
  border-color: rgba(134, 239, 172, 0.2);
}

.compose-grid {
  display: grid;
  grid-template-columns: 1.2fr 0.8fr;
  gap: 20px;
  margin-bottom: 20px;
}

.input-wrapper {
  position: relative;
  display: flex;
  align-items: center;
}

.input-wrapper input {
  width: 100%;
  padding: 12px 16px 12px 40px;
  border-radius: 14px;
  border: 1px solid var(--border);
  background: var(--panel-alt);
  color: var(--text);
  font-size: 14px;
  transition: all 0.2s var(--ease-out);
}

.input-wrapper input:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 4px rgba(125, 211, 252, 0.1);
}

.input-icon {
  position: absolute;
  left: 14px;
  font-size: 16px;
  opacity: 0.7;
}

.status-indicator-box {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  background: var(--panel-alt);
  border: 1px solid var(--border);
  border-radius: 14px;
  height: 46px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--muted);
  position: relative;
}

.status-dot.active {
  background: var(--success);
  box-shadow: 0 0 10px var(--success);
}

.status-dot.active::after {
  content: '';
  position: absolute;
  inset: -4px;
  border-radius: 50%;
  border: 1px solid var(--success);
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0% { transform: scale(1); opacity: 0.8; }
  100% { transform: scale(2.5); opacity: 0; }
}

.status-text {
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
}

.field-textarea textarea {
  width: 100%;
  min-height: 180px;
  padding: 16px;
  border-radius: 16px;
  border: 1px solid var(--border);
  background: var(--panel-alt);
  color: var(--text);
  font-size: 14px;
  line-height: 1.6;
  resize: none;
  transition: all 0.2s var(--ease-out);
}

.field-textarea textarea:focus {
  outline: none;
  border-color: var(--accent);
  background: var(--panel);
}

.compose-footer {
  margin-top: auto;
  padding-top: 14px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.submit-btn {
  width: 100%;
  padding: 14px;
  font-size: 15px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  border-radius: 14px;
}

.compose-tip {
  margin: 0;
  font-size: 12px;
  color: var(--muted);
  text-align: center;
}

.response-status {
  font-size: 11px;
  font-weight: 700;
  padding: 6px 12px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.05);
  color: var(--muted);
  text-transform: uppercase;
}

.response-status.has-data {
  background: rgba(192, 132, 252, 0.1);
  color: var(--accent-2);
}

.response-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.response-header-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
  padding: 0 4px;
}

.response-icon {
  font-size: 18px;
}

.response-label {
  font-size: 13px;
  font-weight: 700;
  color: var(--text);
}

.response-panel {
  flex: 1;
  background: var(--panel-alt);
  border: 1px solid var(--border);
  border-radius: 18px;
  overflow-y: auto;
  position: relative;
}

.response-panel.markdown-body {
  padding: 20px;
  font-size: 14px;
  line-height: 1.7;
  color: var(--text);
}

.response-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 40px;
  border: 2px dashed var(--border);
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.01);
}

.empty-visual {
  position: relative;
  margin-bottom: 24px;
}

.ai-icon-large {
  font-size: 48px;
  z-index: 2;
  position: relative;
}

.pulse-circle {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 80px;
  height: 80px;
  background: radial-gradient(circle, rgba(125, 211, 252, 0.15) 0%, transparent 70%);
  border-radius: 50%;
  animation: pulse-large 3s infinite;
}

@keyframes pulse-large {
  0% { transform: translate(-50%, -50%) scale(0.8); opacity: 0.5; }
  50% { transform: translate(-50%, -50%) scale(1.2); opacity: 1; }
  100% { transform: translate(-50%, -50%) scale(0.8); opacity: 0.5; }
}

.response-empty p {
  color: var(--muted);
  font-size: 14px;
  max-width: 280px;
  line-height: 1.6;
}

.section-divider {
  display: flex;
  align-items: center;
  gap: 20px;
  margin-bottom: 24px;
}

.section-divider::before,
.section-divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--border), transparent);
}

.divider-text {
  font-size: 12px;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.2em;
  color: var(--muted);
}

.ai-grid {
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: 24px;
  align-items: stretch;
}

.optimization-card {
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  height: 100%;
}

.optimization-top {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 8px;
}

.opt-id-block {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
  flex: 1;
}

.opt-id-block h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.timestamp-badge {
  align-self: flex-start;
  margin-top: 4px;
}

.optimization-actions {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}

.delete-icon-btn {
  background: rgba(252, 165, 165, 0.08);
  border: 1px solid rgba(252, 165, 165, 0.2);
  font-size: 16px;
  cursor: pointer;
  padding: 8px;
  border-radius: 10px;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
}

.delete-icon-btn:hover {
  background: rgba(252, 165, 165, 0.18);
  border-color: rgba(252, 165, 165, 0.4);
  transform: scale(1.05);
}

.optimization-meta {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.request-block {
  background: rgba(255, 255, 255, 0.03);
  padding: 16px;
  border-radius: 14px;
  border: 1px solid var(--border);
}

.block-label {
  font-size: 10px;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--muted);
  margin-bottom: 8px;
}

.block-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 6px;
}

.optimization-text {
  font-size: 14px;
  line-height: 1.6;
  margin: 0;
}

.scroll-hint {
  color: var(--muted);
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
  margin-top: -1px;
}

.response-content-modern {
  background: var(--panel-alt);
  border: 1px solid var(--border);
  border-radius: 14px;
  height: 160px;
  overflow-y: auto;
  overflow-x: hidden;
}

.response-content-modern.markdown-body {
  padding: 16px;
  font-size: 13px;
  line-height: 1.65;
  color: var(--text);
}

/* Markdown content inside v-html */
.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3),
.markdown-body :deep(h4) {
  margin: 1em 0 0.5em;
  font-weight: 700;
  color: var(--text);
  line-height: 1.35;
}
.markdown-body :deep(h1) { font-size: 1.35em; }
.markdown-body :deep(h2) { font-size: 1.2em; }
.markdown-body :deep(h3) { font-size: 1.1em; }
.markdown-body :deep(h4) { font-size: 1.05em; }
.markdown-body :deep(p) {
  margin: 0 0 0.85em;
}
.markdown-body :deep(p:last-child) {
  margin-bottom: 0;
}
.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin: 0 0 0.85em;
  padding-left: 1.35em;
}
.markdown-body :deep(li) {
  margin-bottom: 0.35em;
}
.markdown-body :deep(strong),
.markdown-body :deep(b) {
  font-weight: 700;
  color: var(--text);
}
.markdown-body :deep(code) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.92em;
  padding: 0.15em 0.4em;
  border-radius: 6px;
  background: rgba(125, 211, 252, 0.12);
  border: 1px solid rgba(125, 211, 252, 0.2);
}
.markdown-body :deep(pre) {
  margin: 0 0 0.85em;
  padding: 12px 14px;
  border-radius: 10px;
  overflow-x: auto;
  background: rgba(0, 0, 0, 0.25);
  border: 1px solid var(--border);
}
.markdown-body :deep(pre code) {
  padding: 0;
  border: none;
  background: transparent;
  font-size: 12px;
}
.markdown-body :deep(blockquote) {
  margin: 0 0 0.85em;
  padding-left: 12px;
  border-left: 3px solid rgba(125, 211, 252, 0.45);
  color: var(--muted);
}
.markdown-body :deep(a) {
  color: var(--accent);
  text-decoration: underline;
  text-underline-offset: 2px;
}
.markdown-body :deep(hr) {
  margin: 1em 0;
  border: none;
  border-top: 1px solid var(--border);
}
.markdown-body :deep(table) {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
  margin: 0 0 0.85em;
}
.markdown-body :deep(th),
.markdown-body :deep(td) {
  border: 1px solid var(--border);
  padding: 6px 8px;
  text-align: left;
}
.markdown-body :deep(th) {
  background: rgba(255, 255, 255, 0.04);
}

.spinner-small {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

@media (max-width: 1100px) {
  .ai-layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 600px) {
  .compose-grid {
    grid-template-columns: 1fr;
  }
  
  .ai-grid {
    grid-template-columns: 1fr;
  }
}
</style>
