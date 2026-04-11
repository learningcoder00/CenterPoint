<template>
  <section class="hero">
    <div>
      <h1>nuScenes Clip Preview</h1>
      <p>多选卡片后点击底部「开始可视化」提交任务；单击卡片预览帧序列并编辑 tags。</p>
    </div>
    <div class="stats">
      <div class="stat"><span class="label">Clips</span><span class="value">{{ allClips.length || '—' }}</span></div>
      <div class="stat"><span class="label">Frames</span><span class="value">{{ totalFrames || '—' }}</span></div>
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
      <span>🔍</span>
      <input v-model="search" type="text" placeholder="模糊搜索 clip id、token 或 tag…">
      <span v-if="search && filteredClips.length" style="font-size:11px;color:var(--muted);white-space:nowrap;">
        找到 {{ filteredClips.length }} 个结果
      </span>
    </div>
    <button class="btn-secondary" style="padding:10px 16px;border-radius:12px;font-size:13px;cursor:pointer;" @click="selectAllVisible">全选当前页</button>
    <button class="btn-secondary" style="padding:10px 16px;border-radius:12px;font-size:13px;cursor:pointer;" @click="selectedIds.clear()">取消选择</button>
  </section>

  <div v-if="loading" class="loading">Loading clips…</div>
  <div v-else-if="!filteredClips.length" class="empty">No clips match.</div>
  <div v-else class="grid">
    <ClipCard
      v-for="c in filteredClips" :key="c.clip_id"
      :clip="c"
      :selected="selectedIds.has(c.clip_id)"
      :search-query="search"
      :fps="fps"
      @toggle-select="toggleSelect"
      @preview="openPreview"
    />
  </div>

  <!-- selection bar -->
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
import { ref, reactive, computed, onMounted } from 'vue'
import { fetchClips, fetchConfig, fetchTags } from '../api.js'
import { fuzzyScore } from '../utils.js'
import ClipCard from '../components/ClipCard.vue'
import PreviewModal from '../components/PreviewModal.vue'
import SubmitModal from '../components/SubmitModal.vue'

const allClips = ref([])
const loading = ref(true)
const search = ref('')
const fps = ref(3)
const selectedIds = reactive(new Set())
const serverConfig = ref({})
const previewOpen = ref(false)
const previewClipId = ref('')
const showSubmit = ref(false)

const totalFrames = computed(() => allClips.value.reduce((s, c) => s + c.frame_count, 0))

const filteredClips = computed(() => {
  const q = search.value.trim()
  if (!q) return allClips.value
  const results = []
  for (const c of allClips.value) {
    const idScore = fuzzyScore(c.clip_id, q)
    const tokScore = fuzzyScore(c.start_token || '', q)
    const tagScore = (c.tags || []).reduce((best, t) => Math.max(best, fuzzyScore(t, q)), 0)
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
  } catch { /* silent */ }
}

onMounted(async () => {
  try {
    const [clipsData, cfgData] = await Promise.all([fetchClips(), fetchConfig()])
    allClips.value = clipsData.clips || []
    serverConfig.value = cfgData
  } catch { /* empty */ }
  loading.value = false
})
</script>

<style scoped>
.sel-bar {
  display:none;
  position:fixed;
  bottom:28px;
  left:50%;
  transform:translateX(-50%);
  z-index:500;
  gap:14px;
  align-items:center;
  padding:14px 24px;
  border:1px solid var(--selection-bar-border);
  border-radius:18px;
  background:var(--selection-bar-bg);
  backdrop-filter:blur(12px);
  box-shadow:var(--selection-bar-shadow);
  white-space:nowrap;
  transition:
    background .24s var(--ease-out),
    border-color .24s var(--ease-out),
    box-shadow .24s var(--ease-out);
}
.sel-bar.visible { display:flex; }
.sel-bar .count { font-size:15px; font-weight:700; color:var(--accent); }
.sel-bar .btn {
  padding:9px 18px;
  border-radius:10px;
  border:0;
  cursor:pointer;
  font-size:13px;
  font-weight:700;
  transition:
    background .18s var(--ease-out),
    color .18s var(--ease-out),
    transform .18s var(--ease-out);
}
.sel-bar .btn:active { transform: scale(.98); }
.sel-bar .btn-vis { background:var(--accent); color:var(--primary-btn-text); }
.sel-bar .btn-vis:hover { background:var(--primary-btn-hover-bg); }
.sel-bar .btn-clear {
  background:var(--selection-bar-secondary-bg);
  color:var(--selection-bar-secondary-text);
  border:1px solid var(--selection-bar-secondary-border);
}
.sel-bar .btn-clear:hover { background:var(--selection-bar-secondary-hover); color:var(--text); }
.fps-control { min-width:150px; }
.fps-row { display:flex; align-items:center; gap:10px; }
.fps-slider { flex:1; accent-color:var(--accent); cursor:pointer; height:4px; }
</style>
