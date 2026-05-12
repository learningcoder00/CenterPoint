<template>
  <section class="hero">
    <div class="hero-copy">
      <div class="hero-eyebrow">CenterPoint Workflow</div>
      <h1>nuScenes Clip Preview</h1>
      <p>Select clips, Start visualization below — or click a card to preview and edit tags.</p>
    </div>

    <div class="stats">
      <div class="stat dataset-select-wrap" v-if="clipsCatalog.length">
        <span class="label">Dataset</span>
        <select
          class="dataset-select"
          v-model="activeMetaRel"
          :disabled="datasetSwitching"
          @change="onDatasetChange"
          title="clip_preview/clips_meta*.json (pre-generated per infos .pkl)"
        >
          <option v-for="item in clipsCatalog" :key="item.relative_path" :value="item.relative_path">
            {{ datasetOptionLabel(item) }}
          </option>
        </select>
      </div>

      <div class="stat">
        <span class="label">Clips</span>
        <span class="value">{{ allClips.length || '--' }}</span>
      </div>

      <div class="stat">
        <span class="label">Frames</span>
        <span class="value">{{ totalFrames || '--' }}</span>
      </div>

      <div class="stat fps-control">
        <span class="label">Preview FPS</span>
        <div class="fps-row">
          <input type="range" min="1" max="15" step="1" v-model.number="fps" class="fps-slider">
          <span class="value">{{ fps }}</span>
        </div>
      </div>
    </div>
  </section>

  <section class="controls">
    <div class="search-box">
      <div class="search-icon-wrapper">🔍</div>
      <input
        v-model="search"
        type="text"
        :placeholder="searchPlaceholder"
      >
      <div class="filter-btns">
        <button
          v-for="option in searchScopeOptions"
          :key="option.value"
          type="button"
          :class="['filter-btn', { active: searchScope === option.value }]"
          @click="searchScope = option.value"
        >
          {{ option.label }}
        </button>
      </div>
    </div>

    <div class="control-actions">
      <label v-if="sceneOptions.length" class="scene-filter" title="Filter by nuScenes location (when available)">
        <span class="scene-filter__label">📍 Scene</span>
        <select v-model="sceneFilter" class="scene-filter__select">
          <option value="">All scenes</option>
          <option v-for="opt in sceneOptions" :key="opt.value" :value="opt.value">
            {{ opt.label }}
          </option>
        </select>
      </label>
      <button
        type="button"
        :class="['btn-secondary', 'btn-star-filter', { active: starredOnly }]"
        :title="starredOnly ? 'Show all clips' : 'Show only starred clips'"
        @click="starredOnly = !starredOnly"
      >
        <span class="star-icon" :class="{ on: starredOnly }">{{ starredOnly ? '★' : '☆' }}</span>
        Starred ({{ starredCount }})
      </button>
      <button class="btn-secondary" @click="selectAllVisible">Select all visible</button>
      <button class="btn-secondary" @click="selectedIds.clear()">Clear selection</button>
    </div>
  </section>

  <div v-if="loading" class="loading">
    <div class="spinner"></div>
    <div class="loading-text">Loading clips...</div>
  </div>
  <div v-else-if="!filteredClips.length" class="empty">
    <div class="empty-icon">🎬</div>
    <div class="empty-message">
      <template v-if="starredOnly && !starredCount">No starred clips yet — tap the star on any clip to add it to your shortlist.</template>
      <template v-else>No clips match.</template>
    </div>
  </div>
  <div v-else class="grid">
    <ClipCard
      v-for="c in filteredClips"
      :key="c.clip_id"
      :clip="c"
      :selected="selectedIds.has(c.clip_id)"
      :search-query="search"
      :search-scope="searchScope"
      :fps="fps"
      @toggle-select="toggleSelect"
      @preview="openPreview"
      @toggle-star="onToggleStar"
    />
  </div>

  <Teleport to="body">
    <div :class="['sel-bar', { visible: selectedIds.size > 0 }]">
      <span class="count">{{ selectedIds.size }} selected</span>
      <button class="btn-primary" @click="openSubmit('bev_cameras')">Start visualization</button>
      <button class="btn-compare" @click="openSubmit('bev_compare')" title="Run side-by-side BEV with two configs/checkpoints">
        <span class="compare-icon">⇆</span> A/B compare
      </button>
      <button class="btn-secondary" @click="selectedIds.clear()">Clear selection</button>
    </div>
  </Teleport>

  <PreviewModal
    :visible="previewOpen"
    :clip-id="previewClipId"
    :fps="fps"
    @close="previewOpen = false"
    @tags-saved="refreshTags"
  />

  <SubmitModal
    :visible="showSubmit"
    :clip-ids="[...selectedIds]"
    :server-config="serverConfig"
    :default-mode="submitMode"
    @close="showSubmit = false"
    @submitted="selectedIds.clear()"
  />
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { fetchClips, fetchConfig, fetchTags, starClip, switchClipsMeta, unstarClip } from '../api.js'
import { fuzzyScore } from '../utils.js'
import ClipCard from '../components/ClipCard.vue'
import PreviewModal from '../components/PreviewModal.vue'
import SubmitModal from '../components/SubmitModal.vue'

const allClips = ref([])
const loading = ref(true)
const search = ref('')
const searchScope = ref('all')
const starredOnly = ref(false)
const sceneFilter = ref('')
const fps = ref(3)
const selectedIds = reactive(new Set())
const serverConfig = ref({})
const activeMetaRel = ref('')
const datasetSwitching = ref(false)
const starredCount = computed(() => allClips.value.filter(c => c.starred).length)

const sceneOptions = computed(() => {
  const counts = new Map()
  for (const c of allClips.value) {
    const loc = c?.scene?.location
    if (!loc) continue
    counts.set(loc, (counts.get(loc) || 0) + 1)
  }
  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1])
    .map(([value, count]) => ({ value, label: `${value} (${count})` }))
})
const clipsCatalog = computed(() => serverConfig.value.clips_meta_catalog || serverConfig.value.clipsMetaCatalog || [])
const previewOpen = ref(false)
const previewClipId = ref('')
const showSubmit = ref(false)
const submitMode = ref('bev_cameras')

function openSubmit(mode) {
  submitMode.value = mode || 'bev_cameras'
  showSubmit.value = true
}

const searchScopeOptions = [
  { value: 'all', label: 'All' },
  { value: 'clip_id', label: 'clip id' },
  { value: 'start_token', label: 'start token' },
  { value: 'tag', label: 'tag' },
]

const totalFrames = computed(() => allClips.value.reduce((s, c) => s + c.frame_count, 0))
const searchPlaceholder = computed(() => {
  const placeholders = {
    all: 'Search by clip id, start token, or tag',
    clip_id: 'Search by clip id only',
    start_token: 'Search by start token only',
    tag: 'Search by tag only',
  }
  return placeholders[searchScope.value] || placeholders.all
})

const filteredClips = computed(() => {
  let base = allClips.value
  if (starredOnly.value) base = base.filter(c => c.starred)
  if (sceneFilter.value) base = base.filter(c => c?.scene?.location === sceneFilter.value)
  const q = search.value.trim()
  if (!q) return base
  const results = []
  for (const c of base) {
    const idScore = searchScope.value === 'all' || searchScope.value === 'clip_id'
      ? fuzzyScore(c.clip_id, q)
      : 0
    const tokScore = searchScope.value === 'all' || searchScope.value === 'start_token'
      ? fuzzyScore(c.start_token || '', q)
      : 0
    const tagScore = searchScope.value === 'all' || searchScope.value === 'tag'
      ? (c.tags || []).reduce((best, t) => Math.max(best, fuzzyScore(t, q)), 0)
      : 0
    const best = Math.max(idScore, tokScore, tagScore)
    if (best > 0) results.push({ clip: c, score: best })
  }
  results.sort((a, b) => b.score - a.score)
  return results.map(r => r.clip)
})

async function onToggleStar(clip) {
  const wantStar = !clip.starred
  const idx = allClips.value.findIndex(c => c.clip_id === clip.clip_id)
  if (idx !== -1) {
    allClips.value[idx] = { ...allClips.value[idx], starred: wantStar }
  }
  try {
    if (wantStar) await starClip(clip.clip_id)
    else await unstarClip(clip.clip_id)
  } catch (e) {
    if (idx !== -1) {
      allClips.value[idx] = { ...allClips.value[idx], starred: !wantStar }
    }
    alert(`Star update failed: ${e?.message || e}`)
  }
}

function toggleSelect(id) {
  if (selectedIds.has(id)) selectedIds.delete(id)
  else selectedIds.add(id)
}

function selectAllVisible() {
  filteredClips.value.forEach(c => selectedIds.add(c.clip_id))
}

function openPreview(clip) {
  previewClipId.value = clip.clip_id
  previewOpen.value = true
}

async function refreshTags(clipId) {
  try {
    const td = await fetchTags(clipId)
    const idx = allClips.value.findIndex(c => c.clip_id === clipId)
    if (idx !== -1) allClips.value[idx] = { ...allClips.value[idx], tags: td.tags || [] }
  } catch {
    // ignore refresh failures in the preview flow
  }
}

function datasetOptionLabel(item) {
  const dk = item.dataset_key ?? item.datasetKey
  const fn = item.filename
  const clips = item.total_clips != null ? ` (${item.total_clips} clips)` : ''
  if (dk && fn) return `${dk} — ${fn}${clips}`
  return `${fn || item.relative_path || item.relativePath || ''}${clips}`
}

async function onDatasetChange() {
  const rel = activeMetaRel.value
  if (!rel) return
  datasetSwitching.value = true
  try {
    await switchClipsMeta(rel)
    const [clipsData, cfgData] = await Promise.all([fetchClips(), fetchConfig()])
    allClips.value = clipsData.clips || []
    serverConfig.value = cfgData
    activeMetaRel.value = cfgData.clips_meta_active || cfgData.clipsMetaActive || rel
    selectedIds.clear()
  } catch (e) {
    console.error(e)
    alert(e?.message || String(e))
    try {
      const cfgData = await fetchConfig()
      serverConfig.value = cfgData
      activeMetaRel.value = cfgData.clips_meta_active || cfgData.clipsMetaActive || ''
    } catch {
      // ignore
    }
  } finally {
    datasetSwitching.value = false
  }
}

onMounted(async () => {
  try {
    const [clipsData, cfgData] = await Promise.all([fetchClips(), fetchConfig()])
    allClips.value = clipsData.clips || []
    serverConfig.value = cfgData
    activeMetaRel.value = cfgData.clips_meta_active || cfgData.clipsMetaActive || ''
  } catch {
    // loading state falls back to empty
  }
  loading.value = false
})
</script>

<style scoped>
.control-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  align-items: stretch;
  align-self: stretch;
}

.control-actions .btn-secondary {
  height: 100%;
  display: inline-flex;
  align-items: center;
}

.scene-filter {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  border: 1px solid var(--border, rgba(148, 163, 184, 0.32));
  border-radius: 12px;
  background: var(--panel-alt, rgba(15, 23, 42, 0.45));
  font-size: 12px;
  color: var(--text);
  cursor: pointer;
}

.scene-filter__label {
  font-weight: 800;
  letter-spacing: .04em;
  color: var(--muted);
}

.scene-filter__select {
  appearance: none;
  border: none;
  background: transparent;
  color: inherit;
  font-size: 12px;
  font-weight: 700;
  padding: 4px 8px;
  cursor: pointer;
  outline: none;
}

.scene-filter__select option {
  background: var(--panel, #0f172a);
  color: var(--text);
}

.btn-star-filter {
  gap: 6px;
}

.btn-star-filter .star-icon {
  font-size: 16px;
  color: var(--muted);
  transition: color .15s var(--ease-out);
}

.btn-star-filter .star-icon.on {
  color: #fde047;
  text-shadow: 0 0 8px rgba(253, 224, 71, 0.55);
}

.btn-star-filter.active {
  background: linear-gradient(180deg, rgba(253, 224, 71, 0.22), rgba(234, 179, 8, 0.10));
  border-color: rgba(253, 224, 71, 0.5);
  color: #fde047;
}

.dataset-select-wrap {
  min-width: 200px;
  flex-direction: column;
  align-items: stretch;
  gap: 6px;
}

.dataset-select-wrap .label {
  align-self: flex-start;
}

.dataset-select {
  width: 100%;
  max-width: 380px;
  padding: 8px 10px;
  border-radius: 10px;
  border: 1px solid var(--border-subtle, rgba(148, 163, 184, 0.35));
  background: var(--panel-bg, rgba(15, 23, 42, 0.65));
  color: inherit;
  font-size: 13px;
  cursor: pointer;
}

.dataset-select:disabled {
  opacity: 0.55;
  cursor: wait;
}

.sel-bar {
  display: none;
  position: fixed;
  bottom: 28px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 500;
  gap: 16px;
  align-items: center;
  padding: 14px 24px;
  border: 1px solid var(--selection-bar-border);
  border-radius: 20px;
  background: var(--selection-bar-bg);
  backdrop-filter: blur(12px);
  box-shadow: var(--selection-bar-shadow);
  white-space: nowrap;
  transition:
    background .24s var(--ease-out),
    border-color .24s var(--ease-out),
    box-shadow .24s var(--ease-out);
}

.sel-bar.visible {
  display: flex;
}

.sel-bar .count {
  font-size: 15px;
  font-weight: 700;
  color: var(--accent);
  margin-right: 8px;
}

.btn-compare {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 10px 16px;
  border-radius: 12px;
  border: 1px solid rgba(244, 114, 182, 0.45);
  background: linear-gradient(135deg, rgba(56, 189, 248, 0.18), rgba(244, 114, 182, 0.22));
  color: #fce7f3;
  font-weight: 700;
  font-size: 13px;
  cursor: pointer;
  transition: transform .18s var(--ease-out), background .18s var(--ease-out), border-color .18s var(--ease-out);
}
.btn-compare:hover {
  transform: translateY(-1px);
  background: linear-gradient(135deg, rgba(56, 189, 248, 0.28), rgba(244, 114, 182, 0.32));
  border-color: rgba(244, 114, 182, 0.7);
}
.btn-compare .compare-icon {
  font-size: 15px;
  background: linear-gradient(135deg, #38bdf8, #f472b6);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  font-weight: 900;
}

.fps-control {
  min-width: 138px;
}

.fps-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.fps-slider {
  flex: 1;
  accent-color: var(--accent);
  cursor: pointer;
  height: 4px;
}

@media (max-width: 900px) {
  .search-box-upgraded {
    min-height: auto;
  }

  .search-result-pill {
    align-self: flex-start;
  }

  .control-actions {
    width: 100%;
  }

  .control-btn {
    flex: 1;
  }

  .stats-hero {
    width: 100%;
  }

  .search-scope {
    gap: 6px;
  }

  .search-scope-row {
    align-items: flex-start;
    gap: 8px;
  }

  .scope-chip {
    padding: 6px 10px;
  }
}
</style>
