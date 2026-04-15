<template>
  <Teleport to="body">
    <div v-if="visible" class="modal-backdrop" @click.self="$emit('close')">
      <div class="preview-panel">
        <div class="preview-col">
          <img :src="currentSrc" class="preview-img" alt="preview">
          <div class="preview-toolbar">
            <div>
              <p class="toolbar-title">{{ clip?.clip_id }}</p>
              <p class="toolbar-meta">{{ clip?.frame_count }} frames · {{ fmtDuration(clip?.duration_s || 0) }} · {{ fps }} FPS</p>
            </div>
            <div style="display:flex;gap:8px;">
              <button class="modal-btn" @click="togglePlay">{{ playing ? '暂停' : '播放' }}</button>
              <button class="modal-btn secondary" @click="$emit('close')">关闭</button>
            </div>
          </div>
        </div>
        <div class="side-col">
          <h3>Tags</h3>
          <p class="hint">每行一个 tag，保存后即时同步到后端。</p>
          <textarea v-model="tagText" class="tags-input" placeholder="scenic&#10;complex&#10;highway"></textarea>
          <div class="side-actions">
            <button class="btn-primary" style="font-size:13px;padding:8px 18px;" @click="doSaveTags">保存 tags</button>
          </div>
          <p :class="['status-msg', statusType]">{{ statusMsg }}</p>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, watch, onUnmounted } from 'vue'
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
})

watch(() => props.visible, (v) => {
  if (!v) { stopTimer(); document.body.style.overflow = '' }
})

watch(() => props.fps, () => {
  if (playing.value) startPlayTimer()
})

async function doSaveTags() {
  if (!clip.value) return
  const tags = tagText.value.split('\n').map(t => t.trim()).filter(Boolean)
  statusMsg.value = '保存中…'
  statusType.value = ''
  try {
    await saveTags(clip.value.clip_id, tags)
    statusMsg.value = '已保存。'
    statusType.value = 'ok'
    emit('tags-saved', clip.value.clip_id)
    // 自动关闭弹窗
    setTimeout(() => {
      emit('close')
    }, 500)
  } catch (e) {
    statusMsg.value = `保存失败: ${e.message}`
    statusType.value = 'error'
  }
}

onUnmounted(stopTimer)
</script>

<style scoped>
.preview-panel { width:min(1100px,100%); max-height:calc(100vh - 48px); overflow:hidden; display:grid; grid-template-columns:1.2fr 1fr; border-radius:20px; border:1px solid var(--border); background:var(--panel); box-shadow:var(--shadow); }
.preview-col { display:flex; flex-direction:column; background:var(--preview-stage-bg); min-height:0; }
.preview-img { width:100%; flex:1; min-height:280px; object-fit:contain; background:var(--preview-stage-bg); }
.preview-toolbar {
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:10px;
  padding:10px 14px;
  border-top:1px solid var(--preview-toolbar-border);
  background:var(--preview-toolbar-bg);
  color:var(--preview-toolbar-text);
}
.toolbar-title { font-size:13px; font-weight:700; margin:0; color:var(--preview-toolbar-text); }
.toolbar-meta { font-size:12px; color:var(--preview-toolbar-muted); margin:0; }
.modal-btn {
  border:1px solid var(--preview-button-border);
  border-radius:9px;
  background:var(--preview-button-bg);
  color:var(--preview-button-text);
  padding:7px 13px;
  cursor:pointer;
  font-size:12px;
  font-weight:600;
  transition:
    background .18s var(--ease-out),
    color .18s var(--ease-out),
    border-color .18s var(--ease-out),
    transform .18s var(--ease-out);
}
.modal-btn:hover { transform: translateY(-1px); }
.modal-btn.secondary { background:transparent; color:var(--preview-toolbar-text); }
.side-col { display:flex; flex-direction:column; padding:18px; gap:12px; overflow-y:auto; border-left:1px solid var(--border); }
.side-col h3 { margin:0; font-size:15px; }
.hint { margin:0; font-size:11px; color:var(--muted); line-height:1.5; }
.tags-input { width:100%; min-height:130px; resize:vertical; padding:10px; border-radius:10px; border:1px solid var(--border); background:var(--panel-alt); color:var(--text); font-family:inherit; font-size:12px; }
.side-actions { display:flex; gap:8px; flex-wrap:wrap; }
.status-msg { font-size:11px; color:var(--muted); min-height:16px; margin:0; }
.status-msg.error { color:var(--danger); }
.status-msg.ok { color:var(--success); }
@media (max-width:900px) {
  .preview-panel { grid-template-columns:1fr; max-height:none; overflow-y:auto; }
  .side-col { border-left:none; border-top:1px solid var(--border); }
}
</style>
