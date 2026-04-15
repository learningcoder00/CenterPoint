<template>
  <section class="hero">
    <div class="hero-copy">
      <div class="hero-eyebrow">CenterPoint Workflow</div>
      <h1>nuScenes Clip Preview</h1>
      <p>多选卡片后点击底部“开始可视化”提交任务；单击卡片可预览帧序列并编辑 tags。</p>
    </div>

    <div class="stats">
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
      <button class="btn-secondary" @click="selectAllVisible">全选当前结果</button>
      <button class="btn-secondary" @click="selectedIds.clear()">取消选择</button>
    </div>
  </section>

  <div v-if="loading" class="loading">
    <div class="spinner"></div>
    <div class="loading-text">Loading clips...</div>
  </div>
  <div v-else-if="!filteredClips.length" class="empty">
    <div class="empty-icon">🎬</div>
    <div class="empty-message">No clips match.</div>
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
    />
  </div>

  <Teleport to="body">
    <div :class="['sel-bar', { visible: selectedIds.size > 0 }]">
      <span class="count">{{ selectedIds.size }} 个已选</span>
      <button class="btn-primary" @click="showSubmit = true">开始可视化</button>
      <button class="btn-secondary" @click="selectedIds.clear()">取消选择</button>
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
