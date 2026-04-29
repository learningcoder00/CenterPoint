<template>
  <Teleport to="body">
    <div v-if="visible" class="modal-backdrop" @click.self="$emit('close')">
      <div class="submit-panel">
        <h2>Submit visualization job</h2>
        <p class="hint">Runs inference on the selected clips and produces MP4 videos. Please choose the model config and checkpoint for this job.</p>
        <div class="chip-list">
          <span v-for="id in clipIds" :key="id" class="chip">{{ id }}</span>
        </div>

        <div class="field">
          <label>
            Visualization mode <span class="required">(required)</span>
          </label>
          <div class="mode-options">
            <label
              v-for="mode in visualizationModes"
              :key="mode.value"
              :class="['mode-card', { active: visualizationMode === mode.value }]"
            >
              <input v-model="visualizationMode" type="radio" :value="mode.value">
              <span class="mode-title">{{ mode.label }}</span>
              <span class="mode-desc">{{ mode.description }}</span>
            </label>
          </div>
        </div>

        <div class="field">
          <label>
            Config file <span class="required">(required)</span>
          </label>
          <div class="select-shell">
            <select v-model="selectedConfig" @change="applySelectedConfig">
              <option value="" disabled>Select a config from configs/</option>
              <option v-for="path in configOptions" :key="path" :value="path">
                {{ displayPath(path) }}
              </option>
            </select>
          </div>
          <input
            v-model="configVal"
            type="text"
            placeholder="configs/final.py"
            @input="syncSelectedConfig"
          >
          <span class="option-hint">
            {{ configOptions.length }} config option(s) found. The typed path will be submitted.
          </span>
        </div>
        <div class="field">
          <label>
            Checkpoint file <span class="required">(required)</span>
          </label>
          <div class="select-shell">
            <select v-model="selectedCheckpoint" @change="applySelectedCheckpoint">
              <option value="" disabled>Select a checkpoint from project folders</option>
              <option v-for="path in checkpointOptions" :key="path" :value="path">
                {{ displayPath(path) }}
              </option>
            </select>
          </div>
          <input
            v-model="ckptVal"
            type="text"
            placeholder="work_dirs/final/epoch_20.pth"
            @input="syncSelectedCheckpoint"
          >
          <span class="option-hint">
            {{ checkpointOptions.length }} checkpoint option(s) found under work_dirs/, checkpoints/, and weights/.
          </span>
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
const selectedConfig = ref('')
const selectedCheckpoint = ref('')
const visualizationMode = ref('bev_cameras')
const statusMsg = ref('')
const statusType = ref('')
const submitting = ref(false)

const configOptions = computed(() => props.serverConfig.configs || [])
const checkpointOptions = computed(() => props.serverConfig.checkpoints || [])
const visualizationModes = [
  {
    value: 'bev_cameras',
    label: 'BEV + 6 cameras',
    description: 'Current stitched view with BEV and six camera panels.',
  },
  {
    value: 'forward_points',
    label: 'Forward point cloud',
    description: 'Virtual view from (0,0,3), looking forward; points colored by x distance.',
  },
]

watch(() => props.visible, (v) => {
  if (v) {
    selectedConfig.value = ''
    selectedCheckpoint.value = ''
    configVal.value = ''
    ckptVal.value = ''
    visualizationMode.value = 'bev_cameras'
    statusMsg.value = ''
    statusType.value = ''
  }
})

function displayPath(path) {
  const parts = path.split('/')
  const name = parts[parts.length - 1]
  return parts.length > 1 ? `${name} — ${path}` : path
}

function applySelectedConfig() {
  configVal.value = selectedConfig.value
}

function applySelectedCheckpoint() {
  ckptVal.value = selectedCheckpoint.value
}

function syncSelectedConfig() {
  selectedConfig.value = configOptions.value.includes(configVal.value.trim())
    ? configVal.value.trim()
    : ''
}

function syncSelectedCheckpoint() {
  selectedCheckpoint.value = checkpointOptions.value.includes(ckptVal.value.trim())
    ? ckptVal.value.trim()
    : ''
}

async function doSubmit() {
  const effectiveConfig = configVal.value.trim()
  const effectiveCkpt = ckptVal.value.trim()
  if (!effectiveConfig) { statusMsg.value = 'Please choose or enter a config file path.'; statusType.value = 'error'; return }
  if (!effectiveCkpt) { statusMsg.value = 'Please choose or enter a checkpoint file path.'; statusType.value = 'error'; return }

  submitting.value = true
  statusMsg.value = 'Submitting…'
  statusType.value = ''
  try {
    const data = await submitJobs(
      props.clipIds,
      effectiveConfig,
      effectiveCkpt,
      visualizationMode.value,
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
.submit-panel { width:min(620px,100%); border-radius:20px; border:1px solid var(--border); background:var(--panel); padding:28px; box-shadow:var(--shadow); display:flex; flex-direction:column; gap:16px; }
.submit-panel h2 { margin:0; font-size:20px; }
.hint { margin:0; color:var(--muted); font-size:13px; line-height:1.6; }
.chip-list { display:flex; flex-wrap:wrap; gap:6px; }
.chip { padding:5px 11px; border-radius:999px; font-size:12px; font-weight:600; background:rgba(125,211,252,.14); color:var(--accent); border:1px solid rgba(125,211,252,.3); }
.required { color:var(--danger); font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:.04em; }
.mode-options { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px; }
.mode-card { display:flex; flex-direction:column; gap:4px; padding:12px; border:1px solid var(--border); border-radius:12px; background:var(--panel-alt); cursor:pointer; transition:border-color .2s var(--ease-out), background .2s var(--ease-out); }
.mode-card.active { border-color:var(--accent); background:rgba(125,211,252,.12); }
.mode-card input { display:none; }
.mode-title { color:var(--text); font-weight:700; font-size:13px; }
.mode-desc { color:var(--muted); font-size:11px; line-height:1.45; }
.select-shell { position:relative; }
.select-shell::after { content:'▾'; position:absolute; right:13px; top:50%; transform:translateY(-50%); color:var(--muted); pointer-events:none; font-size:12px; }
.select-shell select { width:100%; min-height:40px; border-radius:10px; border:1px solid var(--border); background:var(--panel-alt); color:var(--text); padding:0 36px 0 12px; outline:none; appearance:none; font-size:12px; }
.select-shell select:focus { border-color:var(--accent); box-shadow:0 0 0 3px rgba(125,211,252,.12); }
.field input { margin-top:8px; }
.option-hint { color:var(--muted); font-size:11px; line-height:1.5; }
.submit-actions { display:flex; gap:10px; justify-content:flex-end; }
.status-msg { font-size:11px; color:var(--muted); min-height:16px; margin:0; }
.status-msg.error { color:var(--danger); }
.status-msg.ok { color:var(--success); }
@media (max-width: 640px) { .mode-options { grid-template-columns:1fr; } }
</style>
