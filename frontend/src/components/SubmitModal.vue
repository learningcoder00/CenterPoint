<template>
  <Teleport to="body">
    <div v-if="visible" class="modal-backdrop" @click.self="$emit('close')">
      <div class="submit-panel">
        <h2>Submit visualization job</h2>
        <p class="hint">Runs inference on the selected clips and produces MP4 videos. When jobs finish, open the Results page to view them.</p>
        <div class="chip-list">
          <span v-for="id in clipIds" :key="id" class="chip">{{ id }}</span>
        </div>

        <div class="server-info" v-html="serverInfoHtml"></div>

        <div class="field">
          <label>Config path
            <span v-if="!hasServerConfig" style="color:var(--danger)">(required — no server default)</span>
            <span v-else style="color:var(--success)">(optional — leave blank to use server default)</span>
          </label>
          <input v-model="configVal" type="text" placeholder="configs/nusc_centerpoint_voxelnet_0075voxel_fix_bn_z.py">
        </div>
        <div class="field">
          <label>Checkpoint path
            <span v-if="!hasServerCkpt" style="color:var(--danger)">(required — no server default)</span>
            <span v-else style="color:var(--success)">(optional — leave blank to use server default)</span>
          </label>
          <input v-model="ckptVal" type="text" placeholder="work_dirs/epoch_20.pth">
        </div>
        <p :class="['status-msg', statusType]">{{ statusMsg }}</p>
        <div class="submit-actions">
          <button class="btn-secondary" @click="$emit('close')">Cancel</button>
          <button class="btn-primary" :disabled="submitting" @click="doSubmit">Submit</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { submitJobs } from '../api.js'
import { useRouter } from 'vue-router'

const props = defineProps({
  visible: Boolean,
  clipIds: { type: Array, default: () => [] },
  serverConfig: { type: Object, default: () => ({}) },
})
const emit = defineEmits(['close', 'submitted'])
const router = useRouter()

const configVal = ref('')
const ckptVal = ref('')
const statusMsg = ref('')
const statusType = ref('')
const submitting = ref(false)

const hasServerConfig = computed(() => !!(props.serverConfig.config && props.serverConfig.config.trim()))
const hasServerCkpt = computed(() => !!(props.serverConfig.checkpoint && props.serverConfig.checkpoint.trim()))

const serverInfoHtml = computed(() => {
  const c = props.serverConfig.config || 'not set'
  const k = props.serverConfig.checkpoint || 'not set'
  const cColor = hasServerConfig.value ? 'var(--success)' : 'var(--danger)'
  const kColor = hasServerCkpt.value ? 'var(--success)' : 'var(--danger)'
  let html = `<b style="color:var(--accent)">Server defaults</b><br>Config: <code style="color:${cColor}">${c}</code><br>Checkpoint: <code style="color:${kColor}">${k}</code>`
  if (!hasServerConfig.value || !hasServerCkpt.value) {
    html += `<br><span style="color:var(--warning);font-size:11px;">⚠ No server default for one or both paths — fill in below, or restart the server with --config and --checkpoint.</span>`
  }
  return html
})

watch(() => props.visible, (v) => {
  if (v) {
    configVal.value = props.serverConfig.config || ''
    ckptVal.value = props.serverConfig.checkpoint || ''
    statusMsg.value = ''
    statusType.value = ''
  }
})

async function doSubmit() {
  const effectiveConfig = configVal.value.trim() || props.serverConfig.config || ''
  const effectiveCkpt = ckptVal.value.trim() || props.serverConfig.checkpoint || ''
  if (!effectiveConfig) { statusMsg.value = 'Config path is required'; statusType.value = 'error'; return }
  if (!effectiveCkpt) { statusMsg.value = 'Checkpoint path is required'; statusType.value = 'error'; return }

  submitting.value = true
  statusMsg.value = 'Submitting…'
  statusType.value = ''
  try {
    const data = await submitJobs(
      props.clipIds,
      configVal.value.trim() || undefined,
      ckptVal.value.trim() || undefined,
    )
    statusMsg.value = `Submitted ${data.jobs.length} job(s). Redirecting to Results…`
    statusType.value = 'ok'
    emit('submitted')
    setTimeout(() => { emit('close'); router.push('/results') }, 1500)
  } catch (e) {
    statusMsg.value = `Submit failed: ${e.message}`
    statusType.value = 'error'
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.submit-panel { width:min(540px,100%); border-radius:20px; border:1px solid var(--border); background:var(--panel); padding:28px; box-shadow:var(--shadow); display:flex; flex-direction:column; gap:16px; }
.submit-panel h2 { margin:0; font-size:20px; }
.hint { margin:0; color:var(--muted); font-size:13px; line-height:1.6; }
.chip-list { display:flex; flex-wrap:wrap; gap:6px; }
.chip { padding:5px 11px; border-radius:999px; font-size:12px; font-weight:600; background:rgba(125,211,252,.14); color:var(--accent); border:1px solid rgba(125,211,252,.3); }
.server-info { padding:10px 14px; border-radius:10px; font-size:12px; line-height:1.7; border:1px solid var(--border); background:var(--panel-alt); }
.submit-actions { display:flex; gap:10px; justify-content:flex-end; }
.status-msg { font-size:11px; color:var(--muted); min-height:16px; margin:0; }
.status-msg.error { color:var(--danger); }
.status-msg.ok { color:var(--success); }
</style>
