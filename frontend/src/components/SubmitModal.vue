<template>
  <Teleport to="body">
    <div v-if="visible" class="modal-backdrop" @click.self="$emit('close')">
      <div class="submit-panel">
        <h2>提交可视化任务</h2>
        <p class="hint">将对选中的 clip 执行推理并生成 MP4 视频，任务完成后可在 Results 页面查看。</p>
        <div class="chip-list">
          <span v-for="id in clipIds" :key="id" class="chip">{{ id }}</span>
        </div>

        <div class="server-info" v-html="serverInfoHtml"></div>

        <div class="field">
          <label>Config 路径
            <span v-if="!hasServerConfig" style="color:var(--danger)">（必填，服务器未配置默认值）</span>
            <span v-else style="color:var(--success)">（可选，留空使用服务器默认）</span>
          </label>
          <input v-model="configVal" type="text" placeholder="configs/nusc_centerpoint_voxelnet_0075voxel_fix_bn_z.py">
        </div>
        <div class="field">
          <label>Checkpoint 路径
            <span v-if="!hasServerCkpt" style="color:var(--danger)">（必填，服务器未配置默认值）</span>
            <span v-else style="color:var(--success)">（可选，留空使用服务器默认）</span>
          </label>
          <input v-model="ckptVal" type="text" placeholder="work_dirs/epoch_20.pth">
        </div>
        <p :class="['status-msg', statusType]">{{ statusMsg }}</p>
        <div class="submit-actions">
          <button class="btn-secondary" @click="$emit('close')">取消</button>
          <button class="btn-primary" :disabled="submitting" @click="doSubmit">提交</button>
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
  const c = props.serverConfig.config || '未设置'
  const k = props.serverConfig.checkpoint || '未设置'
  const cColor = hasServerConfig.value ? 'var(--success)' : 'var(--danger)'
  const kColor = hasServerCkpt.value ? 'var(--success)' : 'var(--danger)'
  let html = `<b style="color:var(--accent)">服务器当前默认值</b><br>Config: <code style="color:${cColor}">${c}</code><br>Checkpoint: <code style="color:${kColor}">${k}</code>`
  if (!hasServerConfig.value || !hasServerCkpt.value) {
    html += `<br><span style="color:var(--warning);font-size:11px;">⚠ 服务器未配置默认值，请在下方输入框填写；或重启服务时加上 --config 和 --checkpoint 参数。</span>`
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
  if (!effectiveConfig) { statusMsg.value = '请填写 Config 路径'; statusType.value = 'error'; return }
  if (!effectiveCkpt) { statusMsg.value = '请填写 Checkpoint 路径'; statusType.value = 'error'; return }

  submitting.value = true
  statusMsg.value = '提交中…'
  statusType.value = ''
  try {
    const data = await submitJobs(
      props.clipIds,
      configVal.value.trim() || undefined,
      ckptVal.value.trim() || undefined,
    )
    statusMsg.value = `已提交 ${data.jobs.length} 个任务。跳转到 Results 页面…`
    statusType.value = 'ok'
    emit('submitted')
    setTimeout(() => { emit('close'); router.push('/results') }, 1500)
  } catch (e) {
    statusMsg.value = `提交失败: ${e.message}`
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
