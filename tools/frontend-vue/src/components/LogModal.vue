<template>
  <Teleport to="body">
    <div v-if="visible" class="modal-backdrop" @click.self="$emit('close')">
      <div class="log-panel">
        <div class="log-header">
          <h2>Log: {{ job?.clip_id }} · {{ job?.job_id?.slice(0,8) }}</h2>
          <button class="modal-close" @click="$emit('close')">关闭</button>
        </div>
        <pre ref="logBodyEl" class="log-body">{{ job?.log || '(no log)' }}</pre>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'

defineProps({ visible: Boolean, job: Object })
defineEmits(['close'])

const logBodyEl = ref(null)

watch(() => logBodyEl.value, async (el) => {
  if (el) { await nextTick(); el.scrollTop = el.scrollHeight }
})
</script>

<style scoped>
.log-panel { width:min(760px,100%); max-height:calc(100vh - 80px); display:flex; flex-direction:column; border-radius:20px; border:1px solid var(--border); background:var(--panel); box-shadow:var(--shadow); overflow:hidden; }
.log-header { display:flex; align-items:center; justify-content:space-between; padding:16px 20px; border-bottom:1px solid var(--border); }
.log-header h2 { margin:0; font-size:18px; }
.modal-close { background:transparent; border:1px solid var(--border); border-radius:8px; color:var(--muted); padding:6px 13px; cursor:pointer; font-size:13px; }
.modal-close:hover { color:var(--text); }
.log-body { flex:1; overflow-y:auto; padding:16px 20px; font-family:monospace; font-size:12px; line-height:1.6; color:#c9d1d9; white-space:pre-wrap; background:#0d1117; margin:0; }
</style>
