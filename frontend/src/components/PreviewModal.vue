<template>
  <Teleport to="body">
    <div v-if="visible" class="modal-backdrop" @click.self="$emit('close')">
      <div class="preview-panel">
        <div class="preview-col">
          <div class="preview-stage">
            <img :src="currentSrc" class="preview-img" alt="preview">
            <div class="stage-badge">Clip Preview</div>
            <div class="stage-caption">
              <span>{{ frameLabel }}</span>
              <span>{{ playing ? 'Playing' : 'Paused' }}</span>
            </div>
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
              <button class="modal-btn" @click="togglePlay">{{ playing ? 'Pause' : 'Play' }}</button>
              <button class="modal-btn secondary" @click="$emit('close')">Close</button>
            </div>
          </div>
        </div>
        <div class="side-col">
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
import { computed, ref, watch, onUnmounted } from 'vue'
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

onUnmounted(stopTimer)
</script>

<style scoped>
.preview-panel { width:min(1100px,100%); max-height:calc(100vh - 48px); overflow:hidden; display:grid; grid-template-columns:1.2fr 1fr; border-radius:20px; border:1px solid var(--border); background:var(--panel); box-shadow:var(--shadow); }
.preview-col { display:flex; flex-direction:column; background:var(--preview-stage-bg); min-height:0; }
.preview-stage { position:relative; flex:1; min-height:0; display:flex; align-items:center; justify-content:center; padding:18px 18px 0; }
.preview-img { width:100%; flex:1; min-height:320px; object-fit:contain; border-radius:18px; background:linear-gradient(180deg, rgba(255,255,255,.02), rgba(255,255,255,.01)); }
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
  position:absolute;
  left:30px;
  right:30px;
  bottom:18px;
  display:flex;
  justify-content:space-between;
  gap:12px;
  padding:10px 14px;
  border-radius:14px;
  background:linear-gradient(180deg, rgba(8, 12, 24, 0.24), rgba(8, 12, 24, 0.72));
  color:#e7eefc;
  font-size:12px;
  font-weight:600;
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
.toolbar-actions { display:flex; gap:8px; flex-wrap:wrap; }
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
.side-col { display:flex; flex-direction:column; padding:18px; overflow-y:auto; border-left:1px solid var(--border); background:linear-gradient(180deg, rgba(255,255,255,.01), rgba(255,255,255,.03)); }
.side-card {
  display:flex;
  flex-direction:column;
  gap:14px;
  height:100%;
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
  min-height:210px;
  resize:vertical;
  padding:14px 15px;
  border-radius:14px;
  border:1px solid var(--border);
  background:var(--panel-alt);
  color:var(--text);
  font-family:inherit;
  font-size:13px;
  line-height:1.6;
}
.side-actions { display:flex; flex-direction:column; align-items:flex-start; gap:10px; margin-top:auto; }
.save-btn { font-size:13px; padding:10px 18px; }
.status-msg { font-size:12px; color:var(--muted); min-height:18px; margin:0; }
.status-msg.error { color:var(--danger); }
.status-msg.ok { color:var(--success); }
@media (max-width:900px) {
  .preview-panel { grid-template-columns:1fr; max-height:none; overflow-y:auto; }
  .side-col { border-left:none; border-top:1px solid var(--border); }
  .preview-stage { padding:16px 16px 0; }
  .preview-img { min-height:240px; }
  .preview-toolbar { align-items:flex-start; flex-direction:column; }
  .toolbar-actions { width:100%; }
  .meta-grid { grid-template-columns:1fr; }
  .stage-caption {
    left:24px;
    right:24px;
  }
}
</style>
