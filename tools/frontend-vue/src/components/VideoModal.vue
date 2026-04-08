<template>
  <Teleport to="body">
    <div v-if="visible" class="modal-backdrop" @click.self="close">
      <div class="video-panel">
        <div class="video-header">
          <h2>{{ job?.clip_id }} · {{ job?.job_id?.slice(0,8) }}</h2>
          <button class="modal-close" @click="close">关闭</button>
        </div>
        <div class="video-wrap">
          <video ref="videoEl" class="the-video" controls :src="src"></video>
        </div>
        <div class="video-info">
          <span>Clip: {{ job?.clip_id }}</span>
          <span>Frames: {{ job?.total }}</span>
          <span>Config: {{ fmtPath(job?.config) }}</span>
          <span>Checkpoint: {{ fmtPath(job?.checkpoint) }}</span>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, watch } from 'vue'
import { videoUrl } from '../api.js'
import { fmtPath } from '../utils.js'

const props = defineProps({ visible: Boolean, job: Object })
const emit = defineEmits(['close'])

const videoEl = ref(null)
const src = ref('')

watch(() => props.visible, (v) => {
  if (v && props.job) {
    src.value = videoUrl(props.job.job_id)
    document.body.style.overflow = 'hidden'
  } else {
    if (videoEl.value) { videoEl.value.pause(); videoEl.value.removeAttribute('src') }
    src.value = ''
    document.body.style.overflow = ''
  }
})

function close() {
  emit('close')
}
</script>

<style scoped>
.video-panel { width:min(960px,100%); max-height:calc(100vh - 48px); display:flex; flex-direction:column; border-radius:20px; border:1px solid var(--border); background:var(--panel); box-shadow:var(--shadow); overflow:hidden; }
.video-header { display:flex; align-items:center; justify-content:space-between; padding:16px 20px; border-bottom:1px solid var(--border); flex-shrink:0; }
.video-header h2 { margin:0; font-size:18px; }
.modal-close { background:transparent; border:1px solid var(--border); border-radius:8px; color:var(--muted); padding:6px 13px; cursor:pointer; font-size:13px; }
.modal-close:hover { color:var(--text); }
.video-wrap { flex:1; min-height:0; background:#000; display:flex; align-items:center; justify-content:center; }
.the-video { max-width:100%; max-height:calc(100vh - 180px); display:block; }
.video-info { padding:14px 20px; border-top:1px solid var(--border); font-size:12px; color:var(--muted); display:flex; gap:20px; flex-wrap:wrap; }
</style>
