<template>
  <Teleport to="body">
    <div v-if="visible" class="modal-backdrop" @click.self="$emit('close')">
      <div class="preview-panel">
        <div ref="previewColRef" class="preview-col">
          <div class="preview-stage">
            <img :src="currentSrc" class="preview-img" alt="preview" @load="scheduleMatchSideHeight">
            <div class="stage-badge">Clip Preview</div>
          </div>
          <div class="stage-caption" aria-live="polite">
            <span>{{ frameLabel }}</span>
            <span>{{ playing ? 'Playing' : 'Paused' }}</span>
          </div>
          <div class="preview-toolbar">
            <div class="toolbar-copy">
              <p class="toolbar-title">{{ clip?.clip_id }}</p>
              <div class="toolbar-stats">
                <span class="stat-pill">{{ clip?.frame_count || 0 }} frames</span>
                <span class="stat-pill">{{ fmtDuration(clip?.duration_s || 0) }}</span>
                <span class="stat-pill">{{ fps }} FPS</span>
              </div>
            </div>
            <div class="toolbar-actions">
              <div class="frame-nav" role="group" aria-label="Frame navigation">
                <button
                  type="button"
                  class="modal-btn secondary frame-step"
                  :disabled="!canStepFrames"
                  title="Previous frame (←)"
                  @click="prevFrame"
                >
                  ← Prev
                </button>
                <button
                  type="button"
                  class="modal-btn secondary frame-step"
                  :disabled="!canStepFrames"
                  title="Next frame (→)"
                  @click="nextFrame"
                >
                  Next →
                </button>
              </div>
              <button type="button" class="modal-btn" @click="togglePlay">{{ playing ? 'Pause' : 'Play' }}</button>
              <button type="button" class="modal-btn secondary" @click="$emit('close')">Close</button>
            </div>
          </div>
        </div>
        <div
          class="side-col"
          :class="{ 'side-col--matched': matchSideHeightPx > 0 }"
          :style="sideColStyle"
        >
          <div class="side-card">
            <div class="side-head">
              <div>
                <h3>Tags</h3>
                <p class="hint">One tag per line. Click “Save tags” to persist changes to the server.</p>
              </div>
              <span class="side-badge">{{ tagCount }} tags</span>
            </div>

            <div class="meta-grid">
              <div class="meta-box">
                <span class="meta-label">Clip ID</span>
                <span class="meta-value">{{ clip?.clip_id || '—' }}</span>
              </div>
              <div class="meta-box">
                <span class="meta-label">Current Frame</span>
                <span class="meta-value">{{ frameLabel }}</span>
              </div>
            </div>

            <textarea v-model="tagText" class="tags-input" placeholder="One tag per line&#10;e.g. scenic&#10;complex&#10;highway&#10;&#10;Then click “Save tags”"></textarea>

            <div class="side-actions">
              <button class="btn-primary save-btn" @click="doSaveTags">Save tags</button>
              <p :class="['status-msg', statusType]">{{ statusMsg || 'After editing tags, click “Save tags” to store them. The dialog closes automatically on success.' }}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { computed, ref, watch, onUnmounted, nextTick } from 'vue'
import { fetchClip, fetchTags, saveTags, resolveImgSrc } from '../api.js'
import { fmtDuration } from '../utils.js'

const props = defineProps({ visible: Boolean, clipId: String, fps: { type: Number, default: 3 } })
const emit = defineEmits(['close', 'tags-saved'])

const clip = ref(null)
const frames = ref([])
const frameIdx = ref(0)
const playing = ref(false)
const tagText = ref('')
const statusMsg = ref('')
const statusType = ref('')
let timer = null

const currentSrc = ref('')
const frameLabel = computed(() => {
  if (!frames.value.length) return '—'
  return `${frameIdx.value + 1} / ${frames.value.length}`
})
const tagCount = computed(() =>
  tagText.value.split('\n').map(t => t.trim()).filter(Boolean).length
)

const canStepFrames = computed(() => frames.value.length > 1)

/** 与左侧 preview-col 等高（桌面宽屏）；窄屏为 0 表示不锁定 */
const previewColRef = ref(null)
const matchSideHeightPx = ref(0)
let previewColResizeObserver = null
let winResizeTimer = null

function measureMatchSideHeight() {
  if (!props.visible) {
    matchSideHeightPx.value = 0
    return
  }
  if (typeof window !== 'undefined' && window.innerWidth <= 900) {
    matchSideHeightPx.value = 0
    return
  }
  const el = previewColRef.value
  if (!el) {
    matchSideHeightPx.value = 0
    return
  }
  matchSideHeightPx.value = Math.round(el.getBoundingClientRect().height)
}

function scheduleMatchSideHeight() {
  nextTick(() => {
    measureMatchSideHeight()
    requestAnimationFrame(() => measureMatchSideHeight())
  })
}

const sideColStyle = computed(() => {
  if (matchSideHeightPx.value <= 0) return {}
  return {
    height: `${matchSideHeightPx.value}px`,
    boxSizing: 'border-box',
  }
})

function teardownPreviewColObserver() {
  if (previewColResizeObserver) {
    previewColResizeObserver.disconnect()
    previewColResizeObserver = null
  }
}

function setupPreviewColObserver() {
  teardownPreviewColObserver()
  const el = previewColRef.value
  if (!el || typeof ResizeObserver === 'undefined') return
  previewColResizeObserver = new ResizeObserver(() => scheduleMatchSideHeight())
  previewColResizeObserver.observe(el)
}

function onWindowResizeMatch() {
  if (winResizeTimer) clearTimeout(winResizeTimer)
  winResizeTimer = setTimeout(() => scheduleMatchSideHeight(), 80)
}

function syncCurrentFrameSrc() {
  if (!frames.value.length) return
  const path = frames.value[frameIdx.value]?.image_path
  if (path) currentSrc.value = resolveImgSrc(path)
}

function pausePlaybackForManualStep() {
  stopTimer()
  playing.value = false
}

function prevFrame() {
  if (!canStepFrames.value) return
  pausePlaybackForManualStep()
  const n = frames.value.length
  frameIdx.value = (frameIdx.value - 1 + n) % n
  syncCurrentFrameSrc()
}

function nextFrame() {
  if (!canStepFrames.value) return
  pausePlaybackForManualStep()
  const n = frames.value.length
  frameIdx.value = (frameIdx.value + 1) % n
  syncCurrentFrameSrc()
}

function onPreviewKeydown(e) {
  if (!props.visible) return
  const t = e.target
  if (t && (t.tagName === 'TEXTAREA' || t.tagName === 'INPUT' || t.isContentEditable)) return
  if (e.key === 'ArrowLeft') {
    e.preventDefault()
    prevFrame()
  } else if (e.key === 'ArrowRight') {
    e.preventDefault()
    nextFrame()
  }
}

function stopTimer() { if (timer) { clearInterval(timer); timer = null } }

function startPlayTimer() {
  stopTimer()
  if (frames.value.length > 1) {
    timer = setInterval(() => {
      frameIdx.value = (frameIdx.value + 1) % frames.value.length
      currentSrc.value = resolveImgSrc(frames.value[frameIdx.value].image_path)
    }, Math.round(1000 / props.fps))
  }
}

function togglePlay() {
  playing.value = !playing.value
  stopTimer()
  if (playing.value) startPlayTimer()
}

watch(() => props.visible, async (v) => {
  statusMsg.value = ''
  statusType.value = ''
  if (!v || !props.clipId) { stopTimer(); return }
  try {
    const data = await fetchClip(props.clipId)
    clip.value = data
    frames.value = data.frames || []
    frameIdx.value = 0
    currentSrc.value = frames.value.length ? resolveImgSrc(frames.value[0].image_path) : resolveImgSrc(data.thumbnail_path)
  } catch { /* empty */ }
  try {
    const td = await fetchTags(props.clipId)
    tagText.value = (td.tags || []).join('\n')
  } catch { tagText.value = '' }
  playing.value = true
  startPlayTimer()
  document.body.style.overflow = 'hidden'
  scheduleMatchSideHeight()
})

watch(() => props.visible, (v) => {
  if (!v) {
    stopTimer()
    document.body.style.overflow = ''
    window.removeEventListener('keydown', onPreviewKeydown)
    window.removeEventListener('resize', onWindowResizeMatch)
    teardownPreviewColObserver()
    matchSideHeightPx.value = 0
    if (winResizeTimer) {
      clearTimeout(winResizeTimer)
      winResizeTimer = null
    }
  } else {
    window.addEventListener('keydown', onPreviewKeydown)
    window.addEventListener('resize', onWindowResizeMatch)
    nextTick(() => {
      setupPreviewColObserver()
      scheduleMatchSideHeight()
    })
  }
})

watch(() => props.fps, () => {
  if (playing.value) startPlayTimer()
  scheduleMatchSideHeight()
})

async function doSaveTags() {
  if (!clip.value) return
  const tags = tagText.value.split('\n').map(t => t.trim()).filter(Boolean)
  statusMsg.value = 'Saving…'
  statusType.value = ''
  try {
    await saveTags(clip.value.clip_id, tags)
    statusMsg.value = 'Saved.'
    statusType.value = 'ok'
    emit('tags-saved', clip.value.clip_id)
    // 自动关闭弹窗
    setTimeout(() => {
      emit('close')
    }, 500)
  } catch (e) {
    statusMsg.value = `Save failed: ${e.message}`
    statusType.value = 'error'
  }
}

onUnmounted(() => {
  stopTimer()
  window.removeEventListener('keydown', onPreviewKeydown)
  window.removeEventListener('resize', onWindowResizeMatch)
  teardownPreviewColObserver()
  if (winResizeTimer) clearTimeout(winResizeTimer)
})
</script>

<style scoped>
/* 使用 flex + align-items:flex-start，避免 Grid 行等高拉伸导致左列底部大块空白 */
.preview-panel {
  width:min(1100px,100%);
  max-height:calc(100vh - 48px);
  overflow-x:hidden;
  overflow-y:auto;
  display:flex;
  flex-direction:row;
  align-items:flex-start;
  border-radius:20px;
  border:1px solid var(--border);
  background:var(--panel);
  box-shadow:var(--shadow);
}
.preview-col {
  flex:1.2 1 0;
  min-width:0;
  display:flex;
  flex-direction:column;
  background:var(--preview-stage-bg);
  min-height:0;
  justify-content:flex-start;
}
/* 不要用 flex:1 撑满整列，否则图片会在区域内垂直居中，与下方进度条之间出现大块空隙 */
.preview-stage {
  position:relative;
  flex:0 0 auto;
  min-height:0;
  display:flex;
  align-items:center;
  justify-content:center;
  padding:18px 18px 0;
}
.preview-img {
  display:block;
  width:100%;
  height:auto;
  max-height:min(52vh, 520px);
  min-height:0;
  object-fit:contain;
  border-radius:18px;
  background:linear-gradient(180deg, rgba(255,255,255,.02), rgba(255,255,255,.01));
}
.stage-badge {
  position:absolute;
  top:18px;
  left:30px;
  padding:6px 10px;
  border-radius:999px;
  background:rgba(10, 14, 28, 0.68);
  border:1px solid rgba(255,255,255,.08);
  color:#d9e6ff;
  font-size:11px;
  font-weight:700;
  letter-spacing:.08em;
  text-transform:uppercase;
}
.stage-caption {
  flex-shrink: 0;
  display:flex;
  justify-content:space-between;
  align-items:center;
  gap:12px;
  margin:8px 18px 0;
  padding:10px 14px;
  border-radius:14px;
  background:linear-gradient(180deg, rgba(8, 12, 24, 0.35), rgba(8, 12, 24, 0.85));
  color:#e7eefc;
  font-size:12px;
  font-weight:600;
  border:1px solid rgba(255,255,255,.06);
}
.preview-toolbar {
  display:flex;
  align-items:flex-end;
  justify-content:space-between;
  gap:16px;
  padding:16px 18px 18px;
  border-top:1px solid var(--preview-toolbar-border);
  background:var(--preview-toolbar-bg);
  color:var(--preview-toolbar-text);
}
.toolbar-copy { display:flex; flex-direction:column; gap:10px; min-width:0; }
.toolbar-title { font-size:18px; font-weight:700; margin:0; color:var(--preview-toolbar-text); }
.toolbar-stats { display:flex; flex-wrap:wrap; gap:8px; }
.stat-pill {
  display:inline-flex;
  align-items:center;
  padding:6px 10px;
  border-radius:999px;
  background:rgba(255,255,255,.05);
  border:1px solid rgba(255,255,255,.08);
  color:var(--preview-toolbar-muted);
  font-size:12px;
  font-weight:600;
}
.toolbar-actions { display:flex; gap:8px; flex-wrap:wrap; align-items:center; }
.frame-nav {
  display: inline-flex;
  gap: 6px;
  flex-wrap: wrap;
}
.modal-btn.frame-step:disabled {
  opacity: 0.45;
  cursor: not-allowed;
  transform: none;
}
.modal-btn.frame-step:disabled:hover {
  transform: none;
}
.modal-btn {
  border:1px solid var(--preview-button-border);
  border-radius:10px;
  background:var(--preview-button-bg);
  color:var(--preview-button-text);
  padding:9px 15px;
  cursor:pointer;
  font-size:13px;
  font-weight:600;
  transition:
    background .18s var(--ease-out),
    color .18s var(--ease-out),
    border-color .18s var(--ease-out),
    transform .18s var(--ease-out);
}
.modal-btn:hover { transform: translateY(-1px); }
.modal-btn.secondary { background:transparent; color:var(--preview-toolbar-text); }
.side-col {
  flex:1 1 0;
  min-width:0;
  display:flex;
  flex-direction:column;
  padding:18px;
  overflow-y:auto;
  border-left:1px solid var(--border);
  background:linear-gradient(180deg, rgba(255,255,255,.01), rgba(255,255,255,.03));
}
/* 与左侧等高时：固定高度、Tags 区内部滚动 */
.side-col--matched {
  overflow:hidden;
  align-self:flex-start;
}
.side-col--matched .side-card {
  flex:1 1 0;
  min-height:0;
  height:100%;
  overflow:hidden;
}
.side-col--matched .tags-input {
  flex:1 1 0;
  min-height:0;
  max-height:none;
  resize:none;
}
.side-col--matched .side-head,
.side-col--matched .meta-grid {
  flex-shrink:0;
}
.side-col--matched .side-actions {
  margin-top:0;
  flex-shrink:0;
}
.side-card {
  display:flex;
  flex-direction:column;
  gap:14px;
  height:auto;
  min-height:0;
  padding:18px;
  border-radius:18px;
  border:1px solid rgba(255,255,255,.06);
  background:rgba(255,255,255,.02);
}
.side-head {
  display:flex;
  justify-content:space-between;
  align-items:flex-start;
  gap:12px;
}
.side-col h3 { margin:0 0 4px; font-size:18px; }
.hint { margin:0; font-size:12px; color:var(--muted); line-height:1.6; }
.side-badge {
  display:inline-flex;
  align-items:center;
  justify-content:center;
  padding:6px 10px;
  border-radius:999px;
  background:rgba(125, 211, 252, 0.1);
  color:var(--accent);
  border:1px solid rgba(125, 211, 252, 0.18);
  font-size:12px;
  font-weight:700;
  white-space:nowrap;
}
.meta-grid { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
.meta-box {
  display:flex;
  flex-direction:column;
  gap:6px;
  padding:12px 14px;
  border-radius:14px;
  border:1px solid rgba(255,255,255,.05);
  background:var(--panel-alt);
}
.meta-label {
  font-size:11px;
  text-transform:uppercase;
  letter-spacing:.08em;
  color:var(--muted);
}
.meta-value {
  font-size:13px;
  font-weight:700;
  color:var(--text);
  word-break:break-word;
}
.tags-input {
  width:100%;
  min-height:96px;
  max-height:min(26vh, 168px);
  resize:vertical;
  overflow-y:auto;
  padding:12px 14px;
  border-radius:14px;
  border:1px solid var(--border);
  background:var(--panel-alt);
  color:var(--text);
  font-family:inherit;
  font-size:13px;
  line-height:1.6;
  box-sizing:border-box;
}
.side-actions { display:flex; flex-direction:column; align-items:flex-start; gap:10px; margin-top:auto; }
.save-btn { font-size:13px; padding:10px 18px; }
.status-msg { font-size:12px; color:var(--muted); min-height:18px; margin:0; }
.status-msg.error { color:var(--danger); }
.status-msg.ok { color:var(--success); }
@media (max-width:900px) {
  .preview-panel {
    flex-direction:column;
    align-items:stretch;
    max-height:none;
  }
  .preview-col { flex:1 1 auto; }
  .side-col {
    flex:1 1 auto;
    border-left:none;
    border-top:1px solid var(--border);
  }
  .preview-stage { padding:16px 16px 0; }
  .preview-img { max-height:min(42vh, 380px); }
  .preview-toolbar { align-items:flex-start; flex-direction:column; }
  .toolbar-actions { width:100%; }
  .meta-grid { grid-template-columns:1fr; }
  .stage-caption {
    margin-left:16px;
    margin-right:16px;
  }
}
</style>
