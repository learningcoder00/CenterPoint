<template>
  <div class="home-view">
    <section class="hero">
      <div class="hero-copy">
        <div class="hero-eyebrow">CenterPoint Workspace</div>
        <h1>
          <span class="title-gradient">Perception replay</span>,
          tag-driven review, AI suggestions.
        </h1>
        <p>
          A single workspace that turns scattered nuScenes clips into a structured loop:
          select → visualize → review → ask the model how to improve.
        </p>
        <div class="hero-actions">
          <router-link class="btn-primary hero-cta" to="/clips">
            <span class="cta-icon">🎬</span>
            Browse Clips
          </router-link>
          <router-link class="btn-secondary hero-cta" to="/results">
            <span class="cta-icon">📋</span>
            Open Results
          </router-link>
        </div>
      </div>

      <div class="hero-stack">
        <div class="hero-meta-card">
          <div class="meta-label">Active dataset</div>
          <div class="meta-value mono">{{ datasetLabel }}</div>
          <div class="meta-sub">
            {{ activeClipsMeta || 'No clips_meta loaded yet' }}
          </div>
        </div>
        <div class="hero-meta-card hero-meta-card--accent">
          <div class="meta-label">Pipeline</div>
          <ol class="pipeline">
            <li><span class="pipeline-dot">1</span> Pick clips</li>
            <li><span class="pipeline-dot">2</span> Submit BEV / A-B</li>
            <li><span class="pipeline-dot">3</span> Review verdict</li>
            <li><span class="pipeline-dot">4</span> AI insight</li>
          </ol>
        </div>
      </div>
    </section>

    <section class="kpi-grid">
      <article class="kpi kpi-clips">
        <div class="kpi-head">
          <span class="kpi-icon">🎬</span>
          <span class="kpi-label">Clips indexed</span>
        </div>
        <div class="kpi-value">{{ kpis.clips }}</div>
        <div class="kpi-sub">across {{ datasetCount }} dataset<span v-if="datasetCount !== 1">s</span></div>
        <router-link class="kpi-link" to="/clips">Open Clips →</router-link>
      </article>

      <article class="kpi kpi-running">
        <div class="kpi-head">
          <span class="kpi-icon">⚙</span>
          <span class="kpi-label">In-flight jobs</span>
        </div>
        <div class="kpi-value">{{ kpis.running }}</div>
        <div class="kpi-sub">
          <span class="dot dot-pending"></span> {{ kpis.pending }} pending
          <span class="dot dot-running"></span> {{ kpis.runningOnly }} running
        </div>
        <router-link class="kpi-link" to="/results">Open Results →</router-link>
      </article>

      <article class="kpi kpi-pending">
        <div class="kpi-head">
          <span class="kpi-icon">⚠</span>
          <span class="kpi-label">Awaiting review</span>
        </div>
        <div class="kpi-value">{{ kpis.awaitingReview }}</div>
        <div class="kpi-sub">{{ kpis.issues }} flagged · {{ kpis.clean }} clean</div>
        <router-link class="kpi-link" to="/review?tab=issues">Triage now →</router-link>
      </article>

      <article class="kpi kpi-ai">
        <div class="kpi-head">
          <span class="kpi-icon">✨</span>
          <span class="kpi-label">AI suggestions</span>
        </div>
        <div class="kpi-value">{{ kpis.aiRequests }}</div>
        <div class="kpi-sub">across {{ kpis.aiUniqueClips }} unique clip<span v-if="kpis.aiUniqueClips !== 1">s</span></div>
        <router-link class="kpi-link" to="/ai-optimization">Open AI →</router-link>
      </article>
    </section>

    <section class="section-grid">
      <article class="card timeline-card">
        <div class="card-head">
          <div>
            <div class="section-kicker">Recent activity</div>
            <h2>Latest jobs</h2>
          </div>
          <router-link class="link-more" to="/results">View all →</router-link>
        </div>
        <div v-if="loading" class="muted-center">Loading…</div>
        <div v-else-if="!recentJobs.length" class="muted-center">
          No jobs yet — pick clips and submit a visualization to get started.
        </div>
        <ul v-else class="timeline-list">
          <li v-for="job in recentJobs" :key="job.job_id" class="timeline-item">
            <div :class="['ti-dot', `ti-dot--${job.status}`]"></div>
            <div class="ti-body">
              <div class="ti-row1">
                <span class="ti-clip">{{ job.clip_id }}</span>
              </div>
              <div class="ti-row2">
                <span class="ti-mode">{{ formatVisualizationMode(job.visualization_mode) }}</span>
                <span class="ti-time">{{ fmtTime(job.updated_at || job.created_at) }}</span>
              </div>
            </div>
            <div :class="['ti-side', { 'ti-side--completed': job.status === 'completed' }]">
              <router-link
                v-if="job.status === 'completed'"
                class="ti-cta"
                :to="job.visualization_mode === 'bev_compare' ? '/compare' : '/results'"
              >Open</router-link>
              <span :class="['ti-status', job.status]">{{ fmtStatus(job.status) }}</span>
            </div>
          </li>
        </ul>
      </article>

      <article class="card ai-recent-card">
        <div class="card-head">
          <div>
            <div class="section-kicker">AI memory</div>
            <h2>Recent optimization requests</h2>
          </div>
          <router-link class="link-more" to="/ai-optimization">All requests →</router-link>
        </div>
        <div v-if="loading" class="muted-center">Loading…</div>
        <div v-else-if="!recentOptimizations.length" class="muted-center">
          No AI requests yet — pick a job and ask CenterPoint how to improve.
        </div>
        <ul v-else class="ai-list">
          <li v-for="opt in recentOptimizations" :key="opt.id" class="ai-item">
            <div class="ai-head">
              <span class="ai-job mono">{{ getJobId(opt) || '—' }}</span>
              <span class="ai-when">{{ fmtTime(getCreatedAt(opt)) }}</span>
            </div>
            <p class="ai-desc">{{ truncate(opt.description, 110) || 'No description' }}</p>
          </li>
        </ul>
      </article>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { fetchAIOptimizations, fetchClips, fetchConfig, fetchJobs } from '../api.js'
import { fmtStatus, fmtTime } from '../utils.js'

const clips = ref([])
const jobs = ref([])
const optimizations = ref([])
const serverConfig = ref({})
const loading = ref(true)
let refreshTimer = null

const datasetLabel = computed(() => {
  const catalog = serverConfig.value.clips_meta_catalog || serverConfig.value.clipsMetaCatalog || []
  const active = serverConfig.value.clips_meta_active || serverConfig.value.clipsMetaActive
  const row = catalog.find((r) => r.relative_path === active || r.relativePath === active)
  const dataset = row?.dataset_key || row?.datasetKey
  if (dataset) return dataset
  if (active) return active.split('/').pop().replace(/\.json$/i, '')
  return '—'
})

const activeClipsMeta = computed(() => serverConfig.value.clips_meta_active || serverConfig.value.clipsMetaActive || '')

const datasetCount = computed(() => {
  const catalog = serverConfig.value.clips_meta_catalog || serverConfig.value.clipsMetaCatalog || []
  return catalog.length || 1
})

const kpis = computed(() => {
  const all = jobs.value || []
  const completed = all.filter((j) => j.status === 'completed')
  const resultsCompleted = completed.filter((j) => j.visualization_mode !== 'bev_compare')
  return {
    clips: clips.value.length || serverConfig.value.clip_count || serverConfig.value.clipCount || '—',
    running: all.filter((j) => j.status === 'pending' || j.status === 'running').length,
    runningOnly: all.filter((j) => j.status === 'running').length,
    pending: all.filter((j) => j.status === 'pending').length,
    stitching: all.filter((j) => j.status === 'stitching').length,
    issues: resultsCompleted.filter((j) => j.review_status === 'has_issue').length,
    clean: resultsCompleted.filter((j) => j.review_status === 'no_issue').length,
    awaitingReview: resultsCompleted.filter((j) => !j.review_status || j.review_status === 'unreviewed').length,
    aiRequests: optimizations.value.length,
    aiUniqueClips: new Set(optimizations.value.map((o) => getClipId(o)).filter(Boolean)).size,
  }
})

const recentJobs = computed(() =>
  [...(jobs.value || [])]
    .sort((a, b) => Number(b.updated_at || b.created_at || 0) - Number(a.updated_at || a.created_at || 0))
    .slice(0, 6)
)

const recentOptimizations = computed(() =>
  [...(optimizations.value || [])]
    .sort((a, b) => Number(getCreatedAt(b) || 0) - Number(getCreatedAt(a) || 0))
    .slice(0, 4)
)

function getJobId(opt) { return opt?.jobId ?? opt?.job_id ?? '' }
function getClipId(opt) { return opt?.clipId ?? opt?.clip_id ?? '' }
function getCreatedAt(opt) { return opt?.createdAt ?? opt?.created_at }

function formatVisualizationMode(mode) {
  if (mode === 'forward_points') return 'Forward point cloud'
  if (mode === 'bev_compare') return 'BEV compare (A vs B)'
  return 'BEV + 6 cameras'
}

function truncate(text, max) {
  if (!text) return ''
  return text.length > max ? `${text.slice(0, max - 1)}…` : text
}

async function loadAll(silent = false) {
  if (!silent) loading.value = true
  try {
    const [clipsData, jobData, cfgData, optData] = await Promise.all([
      fetchClips().catch(() => ({ clips: [] })),
      fetchJobs().catch(() => ({ jobs: [] })),
      fetchConfig().catch(() => ({})),
      fetchAIOptimizations().catch(() => ({ optimizations: [] })),
    ])
    clips.value = clipsData.clips || []
    jobs.value = jobData.jobs || []
    serverConfig.value = cfgData || {}
    optimizations.value = optData.optimizations || []
  } finally {
    loading.value = false
  }
  scheduleRefresh()
}

function scheduleRefresh() {
  if (refreshTimer) clearTimeout(refreshTimer)
  const hasActive = (jobs.value || []).some((j) => ['running', 'stitching', 'pending'].includes(j.status))
  if (hasActive) refreshTimer = setTimeout(() => loadAll(true), 5000)
}

onMounted(() => loadAll())
onUnmounted(() => {
  if (refreshTimer) clearTimeout(refreshTimer)
})
</script>

<style scoped>
.home-view {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.hero {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(280px, 1fr);
  gap: 24px;
  align-items: stretch;
  margin-bottom: 2px;
  padding-bottom: 14px;
}

.hero-copy h1 {
  margin: 8px 0 14px;
  font-size: clamp(28px, 3.4vw, 40px);
  line-height: 1.15;
  letter-spacing: -0.03em;
  font-weight: 800;
}

.title-gradient {
  background: linear-gradient(135deg, #38bdf8, #c084fc 60%, #f472b6);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}

.hero-copy p {
  margin: 0 0 22px;
  font-size: 15px;
  color: var(--muted);
  max-width: 580px;
  line-height: 1.6;
}

.hero-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.hero-cta {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 11px 18px;
  border-radius: 14px;
  font-weight: 700;
  font-size: 14px;
  text-decoration: none;
}

.cta-icon { font-size: 16px; }

.hero-stack {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.hero-meta-card {
  border: 1px solid var(--border);
  border-radius: 18px;
  background: var(--card-bg);
  padding: 18px 18px 16px;
  box-shadow: var(--shadow);
}

.hero-meta-card--accent {
  background:
    radial-gradient(360px 200px at 0% 0%, color-mix(in srgb, var(--accent) 16%, transparent), transparent 60%),
    var(--card-bg);
}

.meta-label {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.14em;
  color: var(--muted);
  font-weight: 800;
  margin-bottom: 8px;
}

.meta-value {
  font-size: 18px;
  font-weight: 800;
  color: var(--text);
  word-break: break-word;
}

.meta-value.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 16px;
}

.meta-sub {
  margin-top: 6px;
  font-size: 12px;
  color: var(--muted);
  word-break: break-all;
}

.pipeline {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
  counter-reset: step;
}

.pipeline li {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
  font-weight: 600;
}

.pipeline-dot {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 999px;
  background: linear-gradient(135deg, #38bdf8, #c084fc);
  color: #0a0d16;
  font-size: 11px;
  font-weight: 900;
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
}

.kpi {
  position: relative;
  padding: 18px;
  border-radius: 18px;
  border: 1px solid var(--border);
  background: var(--card-bg);
  box-shadow: var(--shadow);
  display: flex;
  flex-direction: column;
  gap: 10px;
  overflow: hidden;
  transition: transform .2s var(--ease-out), border-color .2s var(--ease-out);
}

.kpi::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, color-mix(in srgb, var(--accent) 14%, transparent), transparent 65%);
  pointer-events: none;
  opacity: .6;
}

.kpi:hover {
  transform: translateY(-2px);
  border-color: color-mix(in srgb, var(--accent) 40%, var(--border));
}

.kpi-head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.kpi-icon { font-size: 18px; }

.kpi-label {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  font-weight: 800;
  color: var(--muted);
}

.kpi-value {
  font-size: 32px;
  font-weight: 800;
  color: var(--text);
  letter-spacing: -0.02em;
}

.kpi-sub {
  font-size: 12px;
  color: var(--muted);
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  display: inline-block;
}

.dot-pending { background: #facc15; box-shadow: 0 0 8px rgba(250, 204, 21, .6); }
.dot-running { background: #38bdf8; box-shadow: 0 0 8px rgba(56, 189, 248, .6); }
.dot-stitching { background: #94a3b8; box-shadow: 0 0 8px rgba(148, 163, 184, .55); }

.kpi-link {
  margin-top: 6px;
  font-size: 12px;
  font-weight: 700;
  color: var(--accent);
  text-decoration: none;
}

.kpi-link:hover { text-decoration: underline; }

.kpi-clips::before { background: linear-gradient(135deg, rgba(56, 189, 248, 0.18), transparent 65%); }
.kpi-running::before { background: linear-gradient(135deg, rgba(99, 102, 241, 0.20), transparent 65%); }
.kpi-pending::before { background: linear-gradient(135deg, rgba(248, 113, 113, 0.20), transparent 65%); }
.kpi-ai::before { background: linear-gradient(135deg, rgba(192, 132, 252, 0.20), transparent 65%); }

.section-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(0, 1fr);
  gap: 18px;
}

.card {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 18px;
  padding: 20px;
  box-shadow: var(--shadow);
}

.card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.card-head h2 {
  margin: 4px 0 0;
  font-size: 18px;
  font-weight: 800;
  letter-spacing: -0.01em;
}

.section-kicker {
  color: var(--accent);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: .15em;
  font-weight: 800;
}

.link-more {
  font-size: 12px;
  color: var(--accent);
  text-decoration: none;
  font-weight: 700;
  white-space: nowrap;
}

.link-more:hover { text-decoration: underline; }

.muted-center {
  color: var(--muted);
  padding: 22px 0;
  text-align: center;
  font-size: 13px;
}

.timeline-list, .ai-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.timeline-item {
  position: relative;
  display: grid;
  grid-template-columns: 12px minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
  padding: 12px 14px;
  border: 1px solid var(--border);
  border-radius: 14px;
  background: var(--panel-alt);
}

.ti-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  margin-top: 2px;
  background: #94a3b8;
}

.ti-dot--running { background: #38bdf8; box-shadow: 0 0 10px rgba(56,189,248,.6); }
.ti-dot--stitching { background: #c084fc; }
.ti-dot--completed { background: #4ade80; box-shadow: 0 0 8px rgba(74,222,128,.45); }
.ti-dot--failed { background: #f87171; }
.ti-dot--pending { background: #facc15; }

.ti-row1 {
  display: flex;
  align-items: center;
  gap: 10px;
  justify-content: space-between;
  flex-wrap: wrap;
}

.ti-side {
  display: inline-flex;
  flex-direction: column;
  align-items: flex-end;
  justify-content: center;
  gap: 6px;
  align-self: center;
}

.ti-side--completed {
  flex-direction: row;
  align-items: center;
  gap: 8px;
}

.ti-clip {
  font-weight: 700;
  color: var(--text);
  max-width: 280px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ti-status {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  padding: 2px 9px;
  border-radius: 999px;
}
.ti-status.completed { background: rgba(74,222,128,.16); color: #4ade80; }
.ti-status.failed { background: rgba(248,113,113,.16); color: #f87171; }
.ti-status.running { background: rgba(56,189,248,.16); color: #38bdf8; }
.ti-status.stitching { background: rgba(192,132,252,.16); color: #c084fc; }
.ti-status.pending { background: rgba(250,204,21,.16); color: #facc15; }
.ti-status.cancelled { background: rgba(251,146,60,.16); color: #fb923c; }

.ti-row2 {
  margin-top: 4px;
  display: flex;
  gap: 14px;
  font-size: 12px;
  color: var(--muted);
  align-items: center;
  flex-wrap: wrap;
}

.ti-cta {
  font-size: 12px;
  font-weight: 700;
  color: var(--accent);
  text-decoration: none;
  white-space: nowrap;
  padding: 4px 10px;
  border-radius: 8px;
  border: 1px solid color-mix(in srgb, var(--accent) 40%, var(--border));
}
.ti-cta:hover { background: color-mix(in srgb, var(--accent) 10%, transparent); }

.ai-item {
  padding: 12px 14px;
  border: 1px solid var(--border);
  border-radius: 14px;
  background: var(--panel-alt);
}

.ai-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 6px;
}

.ai-job {
  font-size: 12px;
  font-weight: 700;
  color: var(--text);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 220px;
}

.ai-when {
  font-size: 11px;
  color: var(--muted);
}

.ai-desc {
  margin: 0;
  font-size: 13px;
  color: var(--muted);
  line-height: 1.5;
}

@media (max-width: 1024px) {
  .hero { grid-template-columns: 1fr; }
  .section-grid { grid-template-columns: 1fr; }
}
</style>
