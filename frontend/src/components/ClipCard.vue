<template>
  <article
    :class="['card', 'clip-card', { selected }]"
    :data-clip-id="clip.clip_id"
    @mouseenter="startHover"
    @mouseleave="stopHover"
  >
    <div class="selection-glow" aria-hidden="true"></div>

    <div class="card-check-wrap">
      <input type="checkbox" :checked="selected" @change.stop="$emit('toggle-select', clip.clip_id)">
    </div>

    <div v-if="selected" class="selected-pill" aria-hidden="true">
      <span class="selected-pill__dot"></span>
      <span>Selected</span>
    </div>

    <div class="preview-shell" @click.stop="$emit('preview', clip)">
      <img class="preview" loading="lazy" :alt="clip.clip_id" :src="imgSrc">
      <div class="preview-overlay">
        <div class="preview-overlay__eyebrow">Clip Preview</div>
      </div>
    </div>

    <div v-if="hoverActive" class="hover-indicator">
      <span class="hover-dot"></span>
      <span>{{ hoverLabel }}</span>
    </div>

    <div class="card-body" @click="$emit('preview', clip)">
      <div class="card-header">
        <div class="card-heading">
          <div class="card-heading__eyebrow">Sequence</div>
          <h2 :class="['card-title', { 'field-hit-text': clipIdMatched, 'field-hit-title': clipIdMatched }]">{{ clip.clip_id }}</h2>
        </div>
        <span class="badge card-badge">{{ clip.frame_count }} frames</span>
      </div>

      <div class="meta">
        <div class="meta-item clip-meta-item">
          <span class="label">Duration</span>
          <span class="value">{{ fmtDuration(clip.duration_s) }}</span>
        </div>
        <div :class="['meta-item', 'clip-meta-item', { 'field-hit-block': tokenMatched }]">
          <span class="label">Start Token</span>
          <span :class="['value', { 'field-hit-text': tokenMatched }]">{{ clip.start_token?.slice(0, 12) }}</span>
        </div>
      </div>
    </div>

    <div class="card-footer">
      <div class="card-footer__header">
        <span class="card-tags-label">Tags</span>
        <span class="card-tags-count">{{ displayTags.length }} tag<span v-if="displayTags.length !== 1">s</span></span>
      </div>
      <div ref="tagListRef" :class="['tag-list', { empty: !displayTags.length }]">
        <span v-for="t in visibleTags" :key="t" :title="t" :class="['tag-chip', { 'tag-hit': isTagHit(t) }]">{{ t }}</span>
        <span v-if="showOverflowChip" class="tag-chip tag-chip-overflow">...</span>
        <template v-if="!displayTags.length">No tags yet</template>
      </div>
    </div>
  </article>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { fetchClip, resolveImgSrc } from '../api.js'
import { fmtDuration, fuzzyScore } from '../utils.js'

const props = defineProps({
  clip: Object,
  selected: Boolean,
  searchQuery: { type: String, default: '' },
  searchScope: { type: String, default: 'all' },
  fps: { type: Number, default: 3 },
})
defineEmits(['toggle-select', 'preview'])

const hoverFrames = ref(null)
const hoverIdx = ref(0)
const hoverActive = ref(false)
const tagListRef = ref(null)
const visibleTags = ref([])
const showOverflowChip = ref(false)
let resizeObserver = null
let hoverTimer = null
let hoverRequestId = 0

const displayTags = computed(() => {
  const tags = props.clip.tags || []
  const seen = new Set()
  return tags.filter((tag) => {
    const key = String(tag || '').trim()
    if (!key || seen.has(key)) return false
    seen.add(key)
    return true
  })
})
const thumbnailSrc = computed(() => resolveImgSrc(props.clip.thumbnail_path))
const imgSrc = ref(thumbnailSrc.value)
const hoverLabel = computed(() => hoverFrames.value ? `${hoverIdx.value + 1}/${hoverFrames.value.length}` : '--')
const normalizedQuery = computed(() => props.searchQuery.trim().toLowerCase())

function includesMatch(text) {
  if (!normalizedQuery.value) return false
  return String(text || '').toLowerCase().includes(normalizedQuery.value)
}

const clipIdMatched = computed(() => {
  if (!normalizedQuery.value) return false
  return (props.searchScope === 'all' || props.searchScope === 'clip_id') &&
    includesMatch(props.clip.clip_id)
})
const tokenMatched = computed(() => {
  if (!normalizedQuery.value) return false
  return (props.searchScope === 'all' || props.searchScope === 'start_token') &&
    includesMatch(props.clip.start_token || '')
})
function isTagHit(t) {
  return (props.searchScope === 'all' || props.searchScope === 'tag') &&
    normalizedQuery.value &&
    includesMatch(t)
}

function measureChipWidth(text) {
  const canvas = measureChipWidth.canvas || (measureChipWidth.canvas = document.createElement('canvas'))
  const ctx = canvas.getContext('2d')
  ctx.font = '600 11px inherit'
  return Math.ceil(ctx.measureText(text).width) + 20
}

async function updateVisibleTags() {
  await nextTick()
  const tags = displayTags.value
  if (!tagListRef.value || !tags.length) {
    visibleTags.value = tags
    showOverflowChip.value = false
    return
  }

  const availableWidth = tagListRef.value.clientWidth
  const gap = 8
  const overflowWidth = measureChipWidth('...')
  const nextVisible = []
  let usedWidth = 0

  for (let i = 0; i < tags.length; i++) {
    const chipWidth = Math.min(measureChipWidth(tags[i]), availableWidth)
    const prefixGap = nextVisible.length ? gap : 0
    const remainingCount = tags.length - i - 1
    const reserveWidth = remainingCount > 0 ? gap + overflowWidth : 0
    if (usedWidth + prefixGap + chipWidth + reserveWidth > availableWidth) break
    usedWidth += prefixGap + chipWidth
    nextVisible.push(tags[i])
  }

  visibleTags.value = nextVisible
  showOverflowChip.value = nextVisible.length < tags.length
}

async function startHover() {
  hoverRequestId += 1
  const requestId = hoverRequestId
  hoverActive.value = true
  if (hoverTimer) {
    clearInterval(hoverTimer)
    hoverTimer = null
  }
  if (!hoverFrames.value) {
    try {
      const d = await fetchClip(props.clip.clip_id)
      if (requestId !== hoverRequestId || !hoverActive.value) return
      hoverFrames.value = d.frames || []
    } catch {
      if (requestId !== hoverRequestId || !hoverActive.value) return
      hoverFrames.value = []
    }
  }
  if (requestId !== hoverRequestId || !hoverActive.value) return
  if (!hoverFrames.value.length) {
    hoverActive.value = false
    return
  }
  hoverIdx.value = 0
  imgSrc.value = resolveImgSrc(hoverFrames.value[0].image_path)
  hoverTimer = setInterval(() => {
    hoverIdx.value = (hoverIdx.value + 1) % hoverFrames.value.length
    imgSrc.value = resolveImgSrc(hoverFrames.value[hoverIdx.value].image_path)
  }, Math.round(1000 / props.fps))
}

function stopHover() {
  hoverRequestId += 1
  hoverActive.value = false
  if (hoverTimer) {
    clearInterval(hoverTimer)
    hoverTimer = null
  }
  imgSrc.value = thumbnailSrc.value
}

watch(thumbnailSrc, (v) => {
  if (!hoverActive.value) imgSrc.value = v
}, { immediate: true })

watch(displayTags, () => {
  updateVisibleTags()
}, { immediate: true })

watch(() => props.fps, () => {
  if (!hoverActive.value || !hoverFrames.value?.length) return
  if (hoverTimer) clearInterval(hoverTimer)
  hoverTimer = setInterval(() => {
    hoverIdx.value = (hoverIdx.value + 1) % hoverFrames.value.length
    imgSrc.value = resolveImgSrc(hoverFrames.value[hoverIdx.value].image_path)
  }, Math.round(1000 / props.fps))
})

onUnmounted(() => {
  if (hoverTimer) clearInterval(hoverTimer)
  if (resizeObserver) resizeObserver.disconnect()
})

onMounted(() => {
  resizeObserver = new ResizeObserver(() => {
    updateVisibleTags()
  })
  if (tagListRef.value) resizeObserver.observe(tagListRef.value)
  updateVisibleTags()
})
</script>

<style scoped>
.clip-card {
  border-width: 1px;
  isolation: isolate;
  transition:
    transform .24s var(--ease-out),
    border-color .24s var(--ease-out),
    box-shadow .24s var(--ease-out),
    background .24s var(--ease-out);
}

.clip-card::before {
  content: '';
  position: absolute;
  inset: 0;
  background:
    radial-gradient(circle at top right, rgba(125, 211, 252, 0.18), transparent 24%),
    linear-gradient(180deg, transparent 52%, rgba(255, 255, 255, 0.02));
  opacity: .9;
  pointer-events: none;
}

.selection-glow {
  position: absolute;
  inset: 0;
  border-radius: inherit;
  background:
    radial-gradient(circle at top left, rgba(125, 211, 252, 0.16), transparent 34%),
    radial-gradient(circle at bottom right, rgba(96, 165, 250, 0.12), transparent 28%);
  opacity: 0;
  transform: scale(0.985);
  transition:
    opacity .24s var(--ease-out),
    transform .24s var(--ease-out);
  pointer-events: none;
  z-index: 0;
}

.clip-card.selected {
  border-color: var(--accent);
  box-shadow:
    0 0 0 2px rgba(125, 211, 252, .22),
    0 16px 36px rgba(22, 38, 68, 0.18),
    0 24px 56px rgba(50, 115, 184, 0.14);
  transform: translateY(-4px);
}

.clip-card.selected .selection-glow {
  opacity: 1;
  transform: scale(1);
}

.clip-card.selected::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  border: 1px solid rgba(125, 211, 252, .38);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, .16);
  pointer-events: none;
  z-index: 1;
}

.card-check-wrap {
  position: absolute;
  top: 12px;
  left: 12px;
  z-index: 12;
}

.card-check-wrap input[type=checkbox] {
  width: 22px;
  height: 22px;
  accent-color: var(--accent);
  cursor: pointer;
  border-radius: 7px;
  box-shadow: 0 8px 20px rgba(10, 16, 28, 0.18);
  transition:
    transform .18s var(--ease-out),
    box-shadow .18s var(--ease-out);
}

.clip-card.selected .card-check-wrap input[type=checkbox] {
  transform: scale(1.06);
  box-shadow:
    0 10px 22px rgba(25, 50, 84, 0.22),
    0 0 0 4px rgba(125, 211, 252, 0.14);
}

.selected-pill {
  position: absolute;
  top: 12px;
  right: 12px;
  z-index: 12;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 11px;
  border-radius: 999px;
  border: 1px solid rgba(125, 211, 252, 0.24);
  background: linear-gradient(180deg, rgba(125, 211, 252, 0.24), rgba(125, 211, 252, 0.14));
  color: var(--accent);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .04em;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.16),
    0 10px 24px rgba(20, 42, 72, 0.14);
  pointer-events: none;
}

.selected-pill__dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: currentColor;
  box-shadow: 0 0 0 4px rgba(125, 211, 252, 0.14);
}

.preview-shell {
  position: relative;
  overflow: hidden;
  cursor: pointer;
}

.preview {
  aspect-ratio: 16/9;
  width: 100%;
  object-fit: cover;
  display: block;
  background: #0a0d16;
  transition:
    transform .45s var(--ease-out),
    filter .28s var(--ease-out);
}

.clip-card:hover .preview {
  transform: scale(1.035);
  filter: saturate(1.04) contrast(1.02);
}

.clip-card.selected .preview {
  filter: saturate(1.08) contrast(1.03);
}

.preview-overlay {
  position: absolute;
  inset: auto 0 0 0;
  padding: 30px 16px 14px;
  background: linear-gradient(180deg, transparent, rgba(7, 11, 20, 0.72));
  color: #f4f8ff;
  pointer-events: none;
}

.preview-overlay__eyebrow {
  font-size: 10px;
  letter-spacing: .16em;
  text-transform: uppercase;
  opacity: .72;
  margin-bottom: 5px;
}

.card-body {
  padding: 16px 16px 8px;
  cursor: pointer;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 14px;
}

.card-heading__eyebrow {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: .14em;
  color: var(--muted);
  margin-bottom: 6px;
}

.card-title {
  margin: 0;
  font-size: 22px;
  line-height: 1;
  letter-spacing: -.03em;
}

.field-hit-text {
  color: #fca5a5;
  text-shadow: 0 0 18px rgba(248, 113, 113, 0.20);
}

.field-hit-title {
  color: #fca5a5;
  font-weight: 800;
  letter-spacing: -.035em;
}

.card-badge {
  align-self: center;
  padding: 7px 11px;
  background: linear-gradient(180deg, rgba(125, 211, 252, .2), rgba(125, 211, 252, .1));
  border: 1px solid rgba(125, 211, 252, .18);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, .12);
}

.clip-card.selected .card-badge {
  background: linear-gradient(180deg, rgba(125, 211, 252, .28), rgba(125, 211, 252, .16));
  border-color: rgba(125, 211, 252, .3);
  color: var(--accent);
}

.clip-meta-item {
  padding: 12px 13px;
  border: 1px solid rgba(125, 211, 252, 0.08);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, .04);
}

.field-hit-block {
  border-color: rgba(248, 113, 113, 0.48);
  background:
    linear-gradient(180deg, rgba(248, 113, 113, 0.22), rgba(239, 68, 68, 0.10));
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, .12),
    0 12px 24px rgba(127, 29, 29, 0.12),
    0 0 0 2px rgba(248, 113, 113, 0.12);
}

.clip-card.selected .clip-meta-item {
  border-color: rgba(125, 211, 252, 0.18);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, .05),
    0 8px 18px rgba(36, 74, 120, 0.06);
}

.clip-meta-item .value {
  font-size: 15px;
}

.card-footer {
  padding: 0 16px 16px;
  border-top: 1px solid rgba(125, 211, 252, 0.08);
}

.card-footer__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding-top: 10px;
}

.card-tags-label {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: .12em;
  color: var(--muted);
}

.card-tags-count {
  font-size: 11px;
  color: var(--muted);
}

.clip-card.selected .card-tags-count,
.clip-card.selected .card-tags-label,
.clip-card.selected .card-heading__eyebrow {
  color: color-mix(in srgb, var(--muted) 70%, var(--accent) 30%);
}

.tag-list {
  margin-top: 6px;
  display: flex;
  flex-wrap: nowrap;
  gap: 8px;
  overflow: hidden;
  min-width: 0;
}

.tag-list.empty {
  color: var(--muted);
  font-size: 11px;
  padding: 8px 10px;
  border-radius: 12px;
  background: rgba(125, 211, 252, 0.05);
}

.tag-chip {
  display: inline-flex;
  align-items: center;
  max-width: 100%;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 0 1 auto;
}

.tag-chip-overflow {
  flex: 0 0 auto;
}

.tag-chip.tag-hit {
  border-color: rgba(239, 68, 68, 0.55);
  background: linear-gradient(180deg, rgba(248, 113, 113, 0.30), rgba(239, 68, 68, 0.16));
  color: #fecaca;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.16),
    0 10px 22px rgba(127, 29, 29, 0.18),
    0 0 0 2px rgba(248, 113, 113, 0.14);
  transform: translateY(-1px);
  font-weight: 700;
}

.hover-indicator {
  position: absolute;
  bottom: 12px;
  right: 12px;
  z-index: 11;
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 5px 9px;
  border-radius: 999px;
  background: var(--hover-indicator-bg);
  backdrop-filter: blur(8px);
  border: 1px solid var(--hover-indicator-border);
  box-shadow: 0 10px 20px rgba(13, 23, 38, 0.10);
  font-size: 11px;
  font-weight: 600;
  color: var(--hover-indicator-text);
  pointer-events: none;
}

.hover-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--accent);
  animation: blink .6s infinite;
}

:root[data-theme='light'] .clip-card.selected {
  box-shadow:
    0 0 0 2px rgba(47, 111, 181, .16),
    0 14px 28px rgba(73, 112, 158, 0.12),
    0 20px 38px rgba(112, 155, 205, 0.12);
}

:root[data-theme='light'] .selected-pill {
  border-color: rgba(47, 111, 181, 0.32);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.72), rgba(235, 245, 255, 0.62));
  color: #2f6fb5;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.5),
    0 10px 20px rgba(101, 137, 181, 0.14),
    0 0 0 1px rgba(255, 255, 255, 0.28);
  backdrop-filter: blur(10px);
}

:root[data-theme='light'] .selected-pill__dot {
  box-shadow: 0 0 0 4px rgba(121, 172, 231, 0.18);
}

:root[data-theme='light'] .field-hit-block {
  border-color: rgba(220, 38, 38, 0.40);
  background:
    linear-gradient(180deg, rgba(254, 202, 202, 0.92), rgba(252, 165, 165, 0.34));
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.22),
    0 12px 22px rgba(239, 68, 68, 0.14),
    0 0 0 2px rgba(252, 165, 165, 0.16);
}

:root[data-theme='light'] .field-hit-footer {
  background:
    linear-gradient(180deg, rgba(121, 172, 231, 0.12), rgba(121, 172, 231, 0.04));
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.2),
    inset 0 0 0 1px rgba(121, 172, 231, 0.08);
}

:root[data-theme='light'] .field-hit-text {
  color: #b91c1c;
  text-shadow: 0 0 16px rgba(248, 113, 113, 0.14);
}

:root[data-theme='light'] .field-hit-title {
  color: #b91c1c;
  font-weight: 800;
}

:root[data-theme='light'] .tag-chip.tag-hit {
  border-color: rgba(220, 38, 38, 0.42);
  background: linear-gradient(180deg, rgba(254, 202, 202, 0.88), rgba(252, 165, 165, 0.62));
  color: #b91c1c;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.3),
    0 10px 18px rgba(239, 68, 68, 0.14),
    0 0 0 2px rgba(252, 165, 165, 0.16);
}
</style>

