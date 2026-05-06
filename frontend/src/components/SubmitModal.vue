<template>
  <Teleport to="body">
    <div v-if="visible" class="modal-backdrop" @click.self="$emit('close')">
      <div :class="['submit-panel', { 'submit-panel--wide': isCompareMode }]">
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

        <div :class="['ab-grid', { 'ab-grid--compare': isCompareMode }]">
          <div class="ab-col">
            <div v-if="isCompareMode" class="ab-col-head">
              <span class="ab-tag ab-tag--a">A</span>
              <span class="ab-col-title">Side A</span>
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
              <span v-if="!isCompareMode" class="option-hint">
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
              <span v-if="!isCompareMode" class="option-hint">
                {{ checkpointOptions.length }} checkpoint option(s) found under work_dirs/, checkpoints/, and weights/.
              </span>
            </div>
          </div>

          <div v-if="isCompareMode" class="ab-col">
            <div class="ab-col-head">
              <span class="ab-tag ab-tag--b">B</span>
              <span class="ab-col-title">Side B</span>
            </div>
            <div class="field">
              <label>
                Config file <span class="required">(required)</span>
              </label>
              <div class="select-shell">
                <select v-model="selectedConfigB" @change="applySelectedConfigB">
                  <option value="" disabled>Select a config from configs/</option>
                  <option v-for="path in configOptions" :key="`b-${path}`" :value="path">
                    {{ displayPath(path) }}
                  </option>
                </select>
              </div>
              <input
                v-model="configBVal"
                type="text"
                placeholder="configs/another.py"
                @input="syncSelectedConfigB"
              >
            </div>
            <div class="field">
              <label>
                Checkpoint file <span class="required">(required)</span>
              </label>
              <div class="select-shell">
                <select v-model="selectedCheckpointB" @change="applySelectedCheckpointB">
                  <option value="" disabled>Select a checkpoint from project folders</option>
                  <option v-for="path in checkpointOptions" :key="`b-${path}`" :value="path">
                    {{ displayPath(path) }}
                  </option>
                </select>
              </div>
              <input
                v-model="ckptBVal"
                type="text"
                placeholder="work_dirs/another/epoch_20.pth"
                @input="syncSelectedCheckpointB"
              >
            </div>
          </div>
        </div>

        <p v-if="isCompareMode" class="ab-hint">
          {{ configOptions.length }} configs · {{ checkpointOptions.length }} checkpoints available. Both sides will run inference on the same frames.
        </p>

        <label class="reuse-toggle" :title="reuseHint">
          <input v-model="reuseCompleted" type="checkbox">
          <span>Reuse already-completed jobs with the same parameters</span>
        </label>

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
  defaultMode: { type: String, default: 'bev_cameras' },
})
const emit = defineEmits(['close', 'submitted'])
const router = useRouter()

const configVal = ref('')
const ckptVal = ref('')
const selectedConfig = ref('')
const selectedCheckpoint = ref('')
const configBVal = ref('')
const ckptBVal = ref('')
const selectedConfigB = ref('')
const selectedCheckpointB = ref('')
const visualizationMode = ref('bev_cameras')
const reuseCompleted = ref(true)
const statusMsg = ref('')
const statusType = ref('')
const submitting = ref(false)
const reuseHint = 'When on, clips that already have a completed job with the exact same parameters '
  + 'will return the existing job instead of running inference again.'

const configOptions = computed(() => props.serverConfig.configs || [])
const checkpointOptions = computed(() => props.serverConfig.checkpoints || [])
const isCompareMode = computed(() => visualizationMode.value === 'bev_compare')
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
  {
    value: 'bev_compare',
    label: 'BEV compare (A vs B)',
    description: 'Two BEVs side by side; cameras shown for context (no boxes).',
  },
]

watch(() => props.visible, (v) => {
  if (v) {
    selectedConfig.value = ''
    selectedCheckpoint.value = ''
    configVal.value = ''
    ckptVal.value = ''
    selectedConfigB.value = ''
    selectedCheckpointB.value = ''
    configBVal.value = ''
    ckptBVal.value = ''
    visualizationMode.value = props.defaultMode || 'bev_cameras'
    reuseCompleted.value = true
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

function applySelectedConfigB() {
  configBVal.value = selectedConfigB.value
}

function applySelectedCheckpointB() {
  ckptBVal.value = selectedCheckpointB.value
}

function syncSelectedConfigB() {
  selectedConfigB.value = configOptions.value.includes(configBVal.value.trim())
    ? configBVal.value.trim()
    : ''
}

function syncSelectedCheckpointB() {
  selectedCheckpointB.value = checkpointOptions.value.includes(ckptBVal.value.trim())
    ? ckptBVal.value.trim()
    : ''
}

async function doSubmit() {
  const effectiveConfig = configVal.value.trim()
  const effectiveCkpt = ckptVal.value.trim()
  if (!effectiveConfig) { statusMsg.value = 'Please choose or enter a config file path.'; statusType.value = 'error'; return }
  if (!effectiveCkpt) { statusMsg.value = 'Please choose or enter a checkpoint file path.'; statusType.value = 'error'; return }

  let effectiveConfigB = ''
  let effectiveCkptB = ''
  if (visualizationMode.value === 'bev_compare') {
    effectiveConfigB = configBVal.value.trim()
    effectiveCkptB = ckptBVal.value.trim()
    if (!effectiveConfigB || !effectiveCkptB) {
      statusMsg.value = 'BEV compare mode needs both side-B config and side-B checkpoint.'
      statusType.value = 'error'
      return
    }
    if (effectiveConfigB === effectiveConfig && effectiveCkptB === effectiveCkpt) {
      statusMsg.value = 'Side A and Side B are identical — both BEVs will be the same.'
      statusType.value = ''
    }
  }

  submitting.value = true
  if (!statusMsg.value || statusType.value === 'error') {
    statusMsg.value = 'Submitting…'
    statusType.value = ''
  }
  try {
    const data = await submitJobs(
      props.clipIds,
      effectiveConfig,
      effectiveCkpt,
      visualizationMode.value,
      effectiveConfigB || undefined,
      effectiveCkptB || undefined,
      reuseCompleted.value,
    )
    const reused = data.reused_count ?? data.jobs.filter(j => j.reused).length
    const fresh = data.new_count ?? (data.jobs.length - reused)
    const breakdown = reused > 0
      ? `Reused ${reused}, queued ${fresh} new. Redirecting to Results…`
      : `Submitted ${fresh} job(s). Redirecting to Results…`
    statusMsg.value = breakdown
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
.submit-panel { width:min(620px,100%); max-height:90vh; overflow-y:auto; border-radius:20px; border:1px solid var(--border); background:var(--panel); padding:28px; box-shadow:var(--shadow); display:flex; flex-direction:column; gap:16px; transition:width .18s var(--ease-out); }
.submit-panel--wide { width:min(880px,100%); }
.submit-panel h2 { margin:0; font-size:20px; }
.hint { margin:0; color:var(--muted); font-size:13px; line-height:1.6; }
.chip-list { display:flex; flex-wrap:wrap; gap:6px; }
.chip { padding:5px 11px; border-radius:999px; font-size:12px; font-weight:600; background:rgba(125,211,252,.14); color:var(--accent); border:1px solid rgba(125,211,252,.3); }
.required { color:var(--danger); font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:.04em; }
.mode-options { display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:10px; }

.ab-grid { display:grid; grid-template-columns:1fr; gap:16px; }
.ab-grid--compare { grid-template-columns:1fr 1fr; gap:18px; }
.ab-col { display:flex; flex-direction:column; gap:14px; min-width:0; }
.ab-col-head { display:flex; align-items:center; gap:8px; padding:8px 12px; border-radius:10px; background:var(--panel-alt); border:1px solid var(--border); }
.ab-col-title { font-size:12px; font-weight:800; letter-spacing:.06em; text-transform:uppercase; color:var(--text); }
.ab-tag { display:inline-flex; align-items:center; justify-content:center; min-width:22px; height:18px; padding:0 6px; border-radius:999px; font-size:10px; font-weight:800; color:#0a0d16; }
.ab-tag--a { background:#38bdf8; }
.ab-tag--b { background:#f472b6; }
.ab-hint { margin:-4px 0 0; color:var(--muted); font-size:11px; line-height:1.5; }
@media (max-width: 720px) { .ab-grid--compare { grid-template-columns:1fr; } }
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
.reuse-toggle { display:flex; align-items:center; gap:8px; font-size:12px; color:var(--muted); cursor:pointer; user-select:none; }
.reuse-toggle input { accent-color:var(--accent); }
.submit-actions { display:flex; gap:10px; justify-content:flex-end; }
.status-msg { font-size:11px; color:var(--muted); min-height:16px; margin:0; }
.status-msg.error { color:var(--danger); }
.status-msg.ok { color:var(--success); }
@media (max-width: 640px) { .mode-options { grid-template-columns:1fr; } }
</style>
