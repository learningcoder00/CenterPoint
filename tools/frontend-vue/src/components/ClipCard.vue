<template>
  <article :class="['card', 'clip-card', { selected }]" :data-clip-id="clip.clip_id"
    @mouseenter="startHover" @mouseleave="stopHover">
    <div class="card-check-wrap">
      <input type="checkbox" :checked="selected" @change.stop="$emit('toggle-select', clip.clip_id)">
    </div>
    <img class="preview" loading="lazy" :alt="clip.clip_id" :src="imgSrc" @click.stop="$emit('preview', clip)">
    <div v-if="hoverActive" class="hover-indicator">
      <span class="hover-dot"></span>
      <span>{{ hoverLabel }}</span>
    </div>
    <div class="card-body" @click="$emit('preview', clip)">
      <div class="card-header">
        <h2 class="card-title">{{ clip.clip_id }}</h2>
        <span class="badge">{{ clip.frame_count }} frames</span>
      </div>
      <div class="meta">
        <div class="meta-item"><span class="label">Duration</span><span class="value">{{ fmtDuration(clip.duration_s) }}</span></div>
        <div class="meta-item"><span class="label">Start Token</span><span class="value">{{ clip.start_token?.slice(0,12) }}</span></div>
      </div>
    </div>
    <div class="card-footer">
      <span class="card-tags-label">Tags</span>
      <div :class="['tag-list', { empty: !displayTags.length }]">
        <span v-for="t in displayTags" :key="t" :class="['tag-chip', { 'tag-hit': isTagHit(t) }]">{{ t }}</span>
        <template v-if="!displayTags.length">—</template>
      </div>
    </div>
  </article>
</template>

<script setup>
import { ref, computed, onUnmounted } from 'vue'
import { fetchClip, resolveImgSrc } from '../api.js'
import { fmtDuration, fuzzyScore } from '../utils.js'

const props = defineProps({
  clip: Object,
  selected: Boolean,
  searchQuery: { type: String, default: '' },
  fps: { type: Number, default: 3 },
})
defineEmits(['toggle-select', 'preview'])

const hoverFrames = ref(null)
const hoverIdx = ref(0)
const hoverActive = ref(false)
let hoverTimer = null

const displayTags = computed(() => props.clip.tags || [])
const thumbnailSrc = computed(() => resolveImgSrc(props.clip.thumbnail_path))
const imgSrc = ref(thumbnailSrc.value)
const hoverLabel = computed(() => hoverFrames.value ? `${hoverIdx.value + 1}/${hoverFrames.value.length}` : '…')

function isTagHit(t) {
  return props.searchQuery && fuzzyScore(t, props.searchQuery) > 0
}

async function startHover() {
  hoverActive.value = true
  if (!hoverFrames.value) {
    try {
      const d = await fetchClip(props.clip.clip_id)
      hoverFrames.value = d.frames || []
    } catch { hoverFrames.value = [] }
  }
  if (!hoverFrames.value.length) { hoverActive.value = false; return }
  hoverIdx.value = 0
  imgSrc.value = resolveImgSrc(hoverFrames.value[0].image_path)
  hoverTimer = setInterval(() => {
    hoverIdx.value = (hoverIdx.value + 1) % hoverFrames.value.length
    imgSrc.value = resolveImgSrc(hoverFrames.value[hoverIdx.value].image_path)
  }, Math.round(1000 / props.fps))
}

function stopHover() {
  hoverActive.value = false
  if (hoverTimer) { clearInterval(hoverTimer); hoverTimer = null }
  imgSrc.value = thumbnailSrc.value
}

import { watch } from 'vue'
watch(thumbnailSrc, (v) => { if (!hoverActive.value) imgSrc.value = v }, { immediate: true })

watch(() => props.fps, () => {
  if (!hoverActive.value || !hoverFrames.value?.length) return
  if (hoverTimer) clearInterval(hoverTimer)
  hoverTimer = setInterval(() => {
    hoverIdx.value = (hoverIdx.value + 1) % hoverFrames.value.length
    imgSrc.value = resolveImgSrc(hoverFrames.value[hoverIdx.value].image_path)
  }, Math.round(1000 / props.fps))
})

onUnmounted(() => { if (hoverTimer) clearInterval(hoverTimer) })
</script>

<style scoped>
.clip-card { border-width:2px; }
.clip-card.selected { border-color:var(--accent); box-shadow:0 0 0 2px rgba(125,211,252,.3), var(--shadow); }
.card-check-wrap { position:absolute; top:10px; left:10px; z-index:10; }
.card-check-wrap input[type=checkbox] { width:20px; height:20px; accent-color:var(--accent); cursor:pointer; }
.preview { aspect-ratio:16/9; width:100%; object-fit:cover; display:block; background:#0a0d16; cursor:pointer; }
.card-body { padding:14px; cursor:pointer; }
.card-header { display:flex; justify-content:space-between; align-items:center; gap:10px; margin-bottom:10px; }
.card-title { margin:0; font-size:16px; }
.card-footer { padding:0 14px 12px; }
.card-tags-label { font-size:10px; text-transform:uppercase; letter-spacing:.08em; color:var(--muted); }
.tag-list.empty { color:var(--muted); font-size:11px; margin-top:5px; }
.tag-list { margin-top:5px; }
.hover-indicator { position:absolute; bottom:8px; right:10px; z-index:9; display:flex; align-items:center; gap:5px; padding:3px 8px; border-radius:999px; background:rgba(10,13,22,.75); backdrop-filter:blur(4px); border:1px solid rgba(125,211,252,.25); font-size:11px; color:var(--accent); pointer-events:none; }
.hover-dot { width:6px; height:6px; border-radius:50%; background:var(--accent); animation:blink .6s infinite; }
</style>
