<template>
  <section class="hero hero-clip">
    <div class="hero-copy">
      <div class="hero-eyebrow">CenterPoint Workflow</div>
      <h1>nuScenes Clip Preview</h1>
      <p>多选卡片后点击底部“开始可视化”提交任务；单击卡片可预览帧序列并编辑 tags。</p>
    </div>

    <div class="stats stats-hero">
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

  <section class="controls controls-upgraded">
    <div class="search-box search-box-upgraded">
      <div class="search-icon" aria-hidden="true">
        <span></span>
      </div>
      <div class="search-copy">
        <span class="search-label">Search clips</span>
        <input
          v-model="search"
          type="text"
          :placeholder="searchPlaceholder"
        >
        <div class="search-scope-row">
          <span class="search-scope-title">搜索范围</span>
          <div class="search-scope" role="tablist" aria-label="搜索范围">
            <button
              v-for="option in searchScopeOptions"
              :key="option.value"
              type="button"
              :class="['scope-chip', { active: searchScope === option.value }]"
              @click="searchScope = option.value"
            >
              {{ option.label }}
            </button>
          </div>
        </div>
      </div>
      <span v-if="search" class="search-result-pill">
        找到 {{ filteredClips.length }} 个结果
      </span>
    </div>

    <div class="control-actions">
      <button class="btn-secondary control-btn" @click="selectAllVisible">全选当前结果</button>
      <button class="btn-secondary control-btn" @click="selectedIds.clear()">取消选择</button>
    </div>
  </section>

  <div v-if="loading" class="loading">Loading clips...</div>
  <div v-else-if="!filteredClips.length" class="empty">No clips match.</div>
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
    />
  </div>

  <Teleport to="body">
    <div :class="['sel-bar', { visible: selectedIds.size > 0 }]">
      <span class="count">{{ selectedIds.size }} 个已选</span>
      <button class="btn btn-vis" @click="showSubmit = true">开始可视化</button>
      <button class="btn btn-clear" @click="selectedIds.clear()">取消选择</button>
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
    @close="showSubmit = false"
    @submitted="selectedIds.clear()"
  />
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { fetchClips, fetchConfig, fetchTags } from '../api.js'
import { fuzzyScore } from '../utils.js'
import ClipCard from '../components/ClipCard.vue'
import PreviewModal from '../components/PreviewModal.vue'
import SubmitModal from '../components/SubmitModal.vue'

const allClips = ref([])
const loading = ref(true)
const search = ref('')
const searchScope = ref('all')
const fps = ref(3)
const selectedIds = reactive(new Set())
const serverConfig = ref({})
const previewOpen = ref(false)
const previewClipId = ref('')
const showSubmit = ref(false)

const searchScopeOptions = [
  { value: 'all', label: '全部' },
  { value: 'clip_id', label: 'clip id' },
  { value: 'start_token', label: 'start token' },
  { value: 'tag', label: 'tag' },
]

const totalFrames = computed(() => allClips.value.reduce((s, c) => s + c.frame_count, 0))
const searchPlaceholder = computed(() => {
  const placeholders = {
    all: '按 clip id、start token 或 tag 模糊搜索',
    clip_id: '仅按 clip id 模糊搜索',
    start_token: '仅按 start token 模糊搜索',
    tag: '仅按 tag 模糊搜索',
  }
  return placeholders[searchScope.value] || placeholders.all
})

const filteredClips = computed(() => {
  const q = search.value.trim()
  if (!q) return allClips.value
  const results = []
  for (const c of allClips.value) {
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

onMounted(async () => {
  try {
    const [clipsData, cfgData] = await Promise.all([fetchClips(), fetchConfig()])
    allClips.value = clipsData.clips || []
    serverConfig.value = cfgData
  } catch {
    // loading state falls back to empty
  }
  loading.value = false
})
</script>

<style scoped>
.hero-clip {
  position: relative;
  overflow: hidden;
}

.hero-clip::before {
  content: '';
  position: absolute;
  inset: 0;
  background:
    radial-gradient(circle at 12% 16%, rgba(125, 211, 252, 0.15), transparent 28%),
    radial-gradient(circle at 88% 18%, rgba(192, 132, 252, 0.12), transparent 26%);
  pointer-events: none;
}

.hero-copy {
  position: relative;
  z-index: 1;
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

.stats-hero {
  position: relative;
  z-index: 1;
  max-width: 460px;
}

.controls-upgraded {
  align-items: stretch;
  gap: 16px;
}

.search-box-upgraded {
  min-height: 74px;
  padding: 12px 18px;
  gap: 14px;
  border-radius: 18px;
}

.search-icon {
  width: 40px;
  height: 40px;
  border-radius: 13px;
  background: rgba(125, 211, 252, 0.12);
  border: 1px solid rgba(125, 211, 252, 0.18);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.search-icon span {
  width: 16px;
  height: 16px;
  border: 2px solid var(--accent);
  border-radius: 50%;
  position: relative;
}

.search-icon span::after {
  content: '';
  position: absolute;
  width: 8px;
  height: 2px;
  right: -5px;
  bottom: -2px;
  background: var(--accent);
  border-radius: 999px;
  transform: rotate(45deg);
  transform-origin: center;
}

.search-copy {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
}

.search-scope-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 2px;
  flex-wrap: wrap;
}

.search-scope-title {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .08em;
  color: var(--muted);
  white-space: nowrap;
}

.search-scope {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.scope-chip {
  padding: 5px 11px;
  border-radius: 999px;
  border: 1px solid rgba(125, 211, 252, 0.14);
  background: rgba(125, 211, 252, 0.05);
  color: var(--muted);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .03em;
  cursor: pointer;
  transition:
    background .18s var(--ease-out),
    border-color .18s var(--ease-out),
    color .18s var(--ease-out),
    transform .18s var(--ease-out),
    box-shadow .18s var(--ease-out);
}

.scope-chip:hover {
  border-color: rgba(125, 211, 252, 0.26);
  color: var(--text);
  transform: translateY(-1px);
}

.scope-chip.active {
  background: rgba(125, 211, 252, 0.16);
  border-color: rgba(125, 211, 252, 0.28);
  color: var(--accent);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08);
}

.search-label {
  color: var(--muted);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: .12em;
  font-weight: 700;
}

.search-result-pill {
  align-self: center;
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(125, 211, 252, 0.12);
  border: 1px solid rgba(125, 211, 252, 0.16);
  color: var(--accent);
  font-size: 11px;
  font-weight: 700;
  white-space: nowrap;
}

.control-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  align-items: stretch;
}

.control-btn {
  min-width: 154px;
  min-height: 74px;
  padding: 0 20px;
  border-radius: 18px;
  font-size: 13px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.sel-bar {
  display: none;
  position: fixed;
  bottom: 28px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 500;
  gap: 14px;
  align-items: center;
  padding: 14px 24px;
  border: 1px solid var(--selection-bar-border);
  border-radius: 18px;
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
}

.sel-bar .btn {
  padding: 9px 18px;
  border-radius: 10px;
  border: 0;
  cursor: pointer;
  font-size: 13px;
  font-weight: 700;
  transition:
    background .18s var(--ease-out),
    color .18s var(--ease-out),
    transform .18s var(--ease-out);
}

.sel-bar .btn:active {
  transform: scale(.98);
}

.sel-bar .btn-vis {
  background: var(--accent);
  color: var(--primary-btn-text);
}

.sel-bar .btn-vis:hover {
  background: var(--primary-btn-hover-bg);
}

.sel-bar .btn-clear {
  background: var(--selection-bar-secondary-bg);
  color: var(--selection-bar-secondary-text);
  border: 1px solid var(--selection-bar-secondary-border);
}

.sel-bar .btn-clear:hover {
  background: var(--selection-bar-secondary-hover);
  color: var(--text);
}

.fps-control {
  min-width: 150px;
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
