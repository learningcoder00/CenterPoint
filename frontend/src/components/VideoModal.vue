<template>
  <div v-if="visible" class="modal-overlay" @click="$emit('close')">
    <div :class="['modal-content', { 'is-expanded': isVideoExpanded }]" @click.stop>
      <div class="modal-header">
        <div>
          <h3>Video Playback</h3>
          <p v-if="job" class="modal-subtitle">{{ job.clip_id }} · {{ job.job_id }}</p>
        </div>
        <div class="modal-header__actions">
          <button class="expand-btn" type="button" @click="isVideoExpanded = !isVideoExpanded">
            {{ isVideoExpanded ? 'Default size' : 'Enlarge video' }}
          </button>
          <button class="close-btn" type="button" @click="$emit('close')">
            <span class="close-icon">×</span>
          </button>
        </div>
      </div>

      <div class="modal-body">
        <div v-if="!job" class="loading">Loading...</div>
        <template v-else>
          <div class="modal-layout">
            <div class="player-panel">
              <div class="video-card">
                <div class="video-container">
                  <video
                    ref="videoRef"
                    autoplay
                    class="video-player"
                    @loadedmetadata="onLoadedMetadata"
                    @timeupdate="onTimeUpdate"
                    @play="isPlaying = true"
                    @pause="isPlaying = false"
                  >
                    <source :src="videoSrc" type="video/mp4">
                    Your browser does not support the video tag.
                  </video>
                </div>

                <div class="player-shell">
                  <div class="progress-header">
                    <span class="marker-title">Issue timeline</span>
                    <span class="marker-hint">Add a bug marker at the current time.</span>
                  </div>

                  <div
                    ref="progressTrackRef"
                    class="progress-track"
                    :class="{ disabled: !duration }"
                    @mousedown="startSeek"
                  >
                    <div class="progress-fill" :style="{ width: `${displayProgressPercent}%` }"></div>
                    <div class="progress-thumb" :style="{ left: `${displayProgressPercent}%` }"></div>
                    <button
                      v-for="marker in sortedMarkers"
                      :key="marker.id"
                      type="button"
                      :class="['marker-bug', `marker-bug--${markerSide(marker)}`]"
                      :style="{ left: `${markerPosition(marker.timeSec)}%` }"
                      :title="markerTooltip(marker)"
                      @click.stop="jumpToMarker(marker)"
                    >
                      🐞
                    </button>
                  </div>

                  <div class="player-controls">
                    <div class="time-readout">
                      <span>{{ formatClock(displayCurrentTime) }}</span>
                      <span>/</span>
                      <span>{{ formatClock(duration) }}</span>
                    </div>

                    <div class="control-buttons">
                      <button type="button" class="player-btn" :disabled="!duration" @click="seekBy(-1)">-1s</button>
                      <button type="button" class="player-btn primary" :disabled="!videoSrc" @click="togglePlay">
                        {{ isPlaying ? 'Pause' : 'Play' }}
                      </button>
                      <button type="button" class="player-btn" :disabled="!duration" @click="seekBy(1)">+1s</button>
                      <div v-if="isCompareJob" class="side-picker" role="group" aria-label="Marker side">
                        <span class="side-picker__label">Side</span>
                        <button
                          v-for="opt in sideOptions"
                          :key="opt.value"
                          type="button"
                          :class="['side-picker__btn', `side-picker__btn--${opt.value}`, { active: nextMarkerSide === opt.value }]"
                          @click="nextMarkerSide = opt.value"
                        >{{ opt.label }}</button>
                      </div>
                      <button type="button" class="player-btn bug-btn" :disabled="!duration" @click="addMarkerAtCurrentTime">
                        Add bug at current time
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div class="side-panel">
              <div v-if="job?.status === 'completed'" class="review-panel">
                <div class="review-panel__head">
                  <div class="section-title">Review verdict</div>
                  <span :class="['verdict-pill', currentVerdictClass]" aria-live="polite">
                    <span class="verdict-pill__dot"></span>
                    {{ reviewStatusLabel }}
                  </span>
                </div>
                <p class="review-hint">Mark this visualization job for triage lists on the Review page.</p>
                <div class="review-actions" role="group" aria-label="Verdict">
                  <button
                    type="button"
                    :class="['review-btn', 'issue', { active: currentReviewStatus === 'has_issue' }]"
                    :disabled="reviewSaving || reviewLoading"
                    @click="applyReview('has_issue')"
                  >
                    <span class="review-btn__icon">⚠</span> Issue
                  </button>
                  <button
                    type="button"
                    :class="['review-btn', 'clean', { active: currentReviewStatus === 'no_issue' }]"
                    :disabled="reviewSaving || reviewLoading"
                    @click="applyReview('no_issue')"
                  >
                    <span class="review-btn__icon">✓</span> Clean
                  </button>
                  <button
                    type="button"
                    :class="['review-btn', 'reset', { active: currentReviewStatus === 'unreviewed' || !currentReviewStatus }]"
                    :disabled="reviewSaving || reviewLoading"
                    @click="applyReview('unreviewed')"
                  >
                    <span class="review-btn__icon">↺</span> Reset
                  </button>
                </div>
                <textarea
                  v-model="reviewerNote"
                  class="review-note"
                  placeholder="Optional verdict note (separate from debug markers note)…"
                  @input="reviewDirty = true"
                />
                <button
                  type="button"
                  class="btn-save-review"
                  :disabled="reviewSaving || reviewLoading || !reviewDirty"
                  @click="saveReviewNoteOnly"
                >
                  {{ reviewSaving ? 'Saving…' : 'Save verdict note' }}
                </button>
                <span v-if="reviewLoading" class="review-status">Loading verdict…</span>
                <span v-else-if="reviewError" class="review-status error">{{ reviewError }}</span>
                <span v-else class="review-status subtle">Current: {{ reviewStatusLabel }}</span>
              </div>

              <div class="video-info">
                <div class="section-title">Job info</div>
                <div class="info-row">
                  <span class="info-label">Clip ID</span>
                  <span class="info-value">{{ job.clip_id }}</span>
                </div>
                <div class="info-row">
                  <span class="info-label">Job ID</span>
                  <span class="info-value">{{ job.job_id }}</span>
                </div>
                <div class="info-row">
                  <span class="info-label">Status</span>
                  <span class="info-value">{{ fmtStatus(job.status) }}</span>
                </div>
                <div class="info-row" v-if="job.completed_at">
                  <span class="info-label">Completed</span>
                  <span class="info-value">{{ fmtTime(job.completed_at) }}</span>
                </div>
                <template v-if="isCompareJob">
                  <div class="info-row info-row--ab">
                    <span class="info-label">
                      <span class="ab-tag ab-tag--a">A</span> Config
                    </span>
                    <span class="info-value mono" :title="job.config || ''">{{ job.config || '—' }}</span>
                  </div>
                  <div class="info-row info-row--ab">
                    <span class="info-label">
                      <span class="ab-tag ab-tag--a">A</span> Checkpoint
                    </span>
                    <span class="info-value mono" :title="job.checkpoint || ''">{{ job.checkpoint || '—' }}</span>
                  </div>
                  <div class="info-row info-row--ab">
                    <span class="info-label">
                      <span class="ab-tag ab-tag--b">B</span> Config
                    </span>
                    <span class="info-value mono" :title="job.config_b || ''">{{ job.config_b || '—' }}</span>
                  </div>
                  <div class="info-row info-row--ab">
                    <span class="info-label">
                      <span class="ab-tag ab-tag--b">B</span> Checkpoint
                    </span>
                    <span class="info-value mono" :title="job.checkpoint_b || ''">{{ job.checkpoint_b || '—' }}</span>
                  </div>
                </template>
              </div>

              <div class="annotation-panel">
              <div class="annotation-head">
                <div>
                  <div class="section-title">Debug note</div>
                  <p class="annotation-hint">Describe the issue you found in this visualization.</p>
                </div>
                <span class="annotation-count">{{ markers.length }} marker<span v-if="markers.length !== 1">s</span></span>
              </div>

              <textarea
                v-model="noteText"
                class="note-input"
                placeholder="e.g. False positive around lane divider, unstable tracking near occlusion..."
                @input="saveState = 'idle'"
              ></textarea>

              <div class="marker-list">
                <div class="marker-list__title">Issue positions</div>
                <div v-if="sortedMarkers.length" class="marker-items">
                  <div v-for="marker in sortedMarkers" :key="marker.id" class="marker-item">
                    <button type="button" class="marker-jump" @click="jumpToMarker(marker)">
                      🐞 {{ formatClock(marker.timeSec) }}
                    </button>
                    <span
                      v-if="isCompareJob"
                      :class="['ab-tag', `ab-tag--${markerSide(marker)}`]"
                      :title="`Side: ${markerSideLabel(marker)}`"
                    >{{ markerSideLabel(marker) }}</span>
                    <button type="button" class="marker-delete" @click="removeMarker(marker.id)">Remove</button>
                  </div>
                </div>
                <div v-else class="marker-empty">No issue markers yet.</div>
              </div>

              <div class="annotation-actions">
                <button type="button" class="btn-save" :disabled="annotationLoading || annotationSaving || !job" @click="saveAnnotations">
                  {{ annotationSaving ? 'Saving...' : 'Save annotations' }}
                </button>
                <span :class="['save-status', saveState]">{{ saveStatusText }}</span>
              </div>
            </div>
          </div>
        </div>
        </template>
      </div>

      <div class="modal-footer">
        <button class="btn-close" type="button" @click="$emit('close')">Close</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, ref, watch, onMounted, onUnmounted } from 'vue'
import { fmtStatus, fmtTime } from '../utils.js'
import { fetchJobAnnotations, saveJobAnnotations, videoUrl, fetchJobReview, setJobReview } from '../api.js'

const props = defineProps({
  visible: Boolean,
  job: Object,
})

const emit = defineEmits(['close', 'review-updated'])

const videoRef = ref(null)
const progressTrackRef = ref(null)

const currentTime = ref(0)
const duration = ref(0)
const isPlaying = ref(false)
const isSeeking = ref(false)
const dragRatio = ref(0)
const wasPlayingBeforeSeek = ref(false)

const noteText = ref('')
const markers = ref([])
const annotationLoading = ref(false)
const annotationSaving = ref(false)
const saveState = ref('idle')
const isVideoExpanded = ref(false)

const nextMarkerSide = ref('both')
const sideOptions = [
  { value: 'a', label: 'A' },
  { value: 'b', label: 'B' },
  { value: 'both', label: 'Both' },
]

const isCompareJob = computed(() => props.job?.visualization_mode === 'bev_compare')

function normalizeSide(raw) {
  const s = String(raw || '').toLowerCase()
  return s === 'a' || s === 'b' || s === 'both' ? s : 'both'
}

function markerSide(marker) {
  return normalizeSide(marker?.side)
}

function markerSideLabel(marker) {
  const s = markerSide(marker)
  if (s === 'a') return 'A'
  if (s === 'b') return 'B'
  return 'A+B'
}

function markerTooltip(marker) {
  const t = `Bug marker at ${formatClock(marker.timeSec)}`
  return isCompareJob.value ? `${t} · side ${markerSideLabel(marker)}` : t
}

const reviewStatus = ref('unreviewed')
const reviewerNote = ref('')
const reviewLoading = ref(false)
const reviewSaving = ref(false)
const reviewError = ref('')
const reviewDirty = ref(false)

const reviewStatusLabel = computed(() => {
  if (reviewStatus.value === 'has_issue') return 'Issue'
  if (reviewStatus.value === 'no_issue') return 'Clean'
  return 'Pending'
})

const currentReviewStatus = computed(() => reviewStatus.value || 'unreviewed')

const currentVerdictClass = computed(() => {
  const s = reviewStatus.value
  if (s === 'has_issue') return 'is-issue'
  if (s === 'no_issue') return 'is-clean'
  return 'is-pending'
})

const videoSrc = computed(() => {
  const jobId = props.job?.job_id
  return jobId ? videoUrl(jobId) : ''
})

const sortedMarkers = computed(() =>
  [...markers.value].sort((a, b) => a.timeSec - b.timeSec)
)

const displayCurrentTime = computed(() => {
  if (isSeeking.value && duration.value > 0) return dragRatio.value * duration.value
  return currentTime.value
})

const displayProgressPercent = computed(() => {
  if (!duration.value) return 0
  const ratio = isSeeking.value ? dragRatio.value : currentTime.value / duration.value
  return Math.max(0, Math.min(100, ratio * 100))
})

const saveStatusText = computed(() => {
  if (annotationLoading.value) return 'Loading annotations...'
  if (annotationSaving.value) return 'Saving annotations...'
  if (saveState.value === 'saved') return 'Saved.'
  if (saveState.value === 'error') return 'Save failed.'
  return 'Markers and note are saved per video job.'
})

function clamp01(v) {
  return Math.max(0, Math.min(1, v))
}

function markerPosition(timeSec) {
  if (!duration.value) return 0
  return clamp01(timeSec / duration.value) * 100
}

function formatClock(value) {
  const total = Math.max(0, Math.floor(Number(value || 0)))
  const min = Math.floor(total / 60)
  const sec = total % 60
  return `${String(min).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
}

function makeMarkerId() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID()
  return `bug_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
}

async function loadReview() {
  const jobId = props.job?.job_id
  if (!jobId || props.job?.status !== 'completed') return
  reviewLoading.value = true
  reviewError.value = ''
  try {
    const data = await fetchJobReview(jobId)
    reviewStatus.value = data.review_status || 'unreviewed'
    reviewerNote.value = data.reviewer_note || ''
    reviewDirty.value = false
  } catch (e) {
    reviewError.value = 'Failed to load verdict'
    reviewStatus.value = 'unreviewed'
    reviewerNote.value = ''
    console.error(e)
  } finally {
    reviewLoading.value = false
  }
}

async function applyReview(status) {
  const jobId = props.job?.job_id
  if (!jobId) return
  reviewSaving.value = true
  reviewError.value = ''
  try {
    const data = await setJobReview(jobId, status, reviewerNote.value)
    reviewStatus.value = data.review_status || status
    reviewerNote.value = data.reviewer_note || ''
    reviewDirty.value = false
    emit('review-updated', {
      jobId,
      reviewStatus: reviewStatus.value,
      reviewerNote: reviewerNote.value,
    })
  } catch (e) {
    reviewError.value = e?.message || 'Save failed'
  } finally {
    reviewSaving.value = false
  }
}

async function saveReviewNoteOnly() {
  const jobId = props.job?.job_id
  if (!jobId) return
  reviewSaving.value = true
  reviewError.value = ''
  try {
    const data = await setJobReview(jobId, reviewStatus.value, reviewerNote.value)
    reviewerNote.value = data.reviewer_note || ''
    reviewDirty.value = false
    emit('review-updated', {
      jobId,
      reviewStatus: data.review_status || reviewStatus.value,
      reviewerNote: reviewerNote.value,
    })
  } catch (e) {
    reviewError.value = e?.message || 'Save failed'
  } finally {
    reviewSaving.value = false
  }
}

async function loadAnnotations() {
  const jobId = props.job?.job_id
  if (!jobId) return
  annotationLoading.value = true
  try {
    const data = await fetchJobAnnotations(jobId)
    noteText.value = data.note || ''
    markers.value = Array.isArray(data.markers)
      ? data.markers.map((m) => ({ ...m, side: normalizeSide(m?.side) }))
      : []
    saveState.value = 'idle'
  } catch (e) {
    noteText.value = ''
    markers.value = []
    saveState.value = 'error'
    console.error('Failed to load annotations:', e)
  } finally {
    annotationLoading.value = false
  }
}

async function saveAnnotations() {
  const jobId = props.job?.job_id
  if (!jobId) return
  annotationSaving.value = true
  saveState.value = 'idle'
  try {
    const data = await saveJobAnnotations(jobId, noteText.value, sortedMarkers.value)
    noteText.value = data.note || ''
    markers.value = Array.isArray(data.markers)
      ? data.markers.map((m) => ({ ...m, side: normalizeSide(m?.side) }))
      : []
    saveState.value = 'saved'
  } catch (e) {
    saveState.value = 'error'
    console.error('Failed to save annotations:', e)
  } finally {
    annotationSaving.value = false
  }
}

function seekToTime(timeSec) {
  if (!videoRef.value || !duration.value) return
  const next = Math.max(0, Math.min(duration.value, timeSec))
  videoRef.value.currentTime = next
  currentTime.value = next
}

function seekBy(delta) {
  seekToTime(currentTime.value + delta)
}

function togglePlay() {
  if (!videoRef.value) return
  if (videoRef.value.paused) {
    videoRef.value.play().catch((e) => console.log('Video play failed:', e))
  } else {
    videoRef.value.pause()
  }
}

function addMarkerAtTime(timeSec) {
  if (!duration.value) return
  markers.value = [
    ...markers.value,
    {
      id: makeMarkerId(),
      timeSec: Math.max(0, Math.min(duration.value, Number(timeSec || 0))),
      type: 'bug',
      side: isCompareJob.value ? nextMarkerSide.value : 'both',
    },
  ]
  saveState.value = 'idle'
}

function addMarkerAtCurrentTime() {
  addMarkerAtTime(currentTime.value)
}

function jumpToMarker(marker) {
  seekToTime(marker.timeSec)
}

function removeMarker(markerId) {
  markers.value = markers.value.filter((marker) => marker.id !== markerId)
  saveState.value = 'idle'
}

function onLoadedMetadata() {
  if (!videoRef.value) return
  duration.value = Number.isFinite(videoRef.value.duration) ? videoRef.value.duration : 0
  currentTime.value = videoRef.value.currentTime || 0
}

function onTimeUpdate() {
  if (isSeeking.value || !videoRef.value) return
  currentTime.value = videoRef.value.currentTime || 0
}

function getProgressRatio(clientX) {
  const rect = progressTrackRef.value?.getBoundingClientRect()
  if (!rect || !rect.width) return 0
  return clamp01((clientX - rect.left) / rect.width)
}

function updateSeekFromPointer(clientX) {
  const ratio = getProgressRatio(clientX)
  dragRatio.value = ratio
  if (duration.value) {
    const nextTime = ratio * duration.value
    currentTime.value = nextTime
    if (videoRef.value) videoRef.value.currentTime = nextTime
  }
}

function onGlobalMouseMove(e) {
  if (!isSeeking.value) return
  updateSeekFromPointer(e.clientX)
}

function stopSeek() {
  if (!isSeeking.value) return
  isSeeking.value = false
  if (wasPlayingBeforeSeek.value && videoRef.value) {
    videoRef.value.play().catch(() => {})
  }
  wasPlayingBeforeSeek.value = false
  window.removeEventListener('mousemove', onGlobalMouseMove)
  window.removeEventListener('mouseup', stopSeek)
}

function startSeek(e) {
  if (!duration.value) return
  wasPlayingBeforeSeek.value = !!videoRef.value && !videoRef.value.paused
  if (videoRef.value) videoRef.value.pause()
  isSeeking.value = true
  updateSeekFromPointer(e.clientX)
  window.addEventListener('mousemove', onGlobalMouseMove)
  window.addEventListener('mouseup', stopSeek)
}

function resetPlayerState() {
  currentTime.value = 0
  duration.value = 0
  isPlaying.value = false
  isSeeking.value = false
  dragRatio.value = 0
}

function resetAnnotationState() {
  noteText.value = ''
  markers.value = []
  annotationLoading.value = false
  annotationSaving.value = false
  saveState.value = 'idle'
  nextMarkerSide.value = 'both'
}

function resetReviewState() {
  reviewStatus.value = 'unreviewed'
  reviewerNote.value = ''
  reviewLoading.value = false
  reviewSaving.value = false
  reviewError.value = ''
  reviewDirty.value = false
}

function onKeydown(e) {
  if (e.key === 'Escape') emit('close')
}

watch(
  () => [props.visible, props.job?.job_id],
  async ([visible]) => {
    if (!visible) {
      if (videoRef.value) videoRef.value.pause()
      resetPlayerState()
      resetAnnotationState()
      resetReviewState()
      return
    }

    await nextTick()
    await Promise.all([loadAnnotations(), loadReview()])

    if (!videoRef.value || !videoSrc.value) return
    videoRef.value.load()
    videoRef.value.play().catch((e) => console.log('Video play failed:', e))
  }
)

onMounted(() => {
  window.addEventListener('keydown', onKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
  window.removeEventListener('mousemove', onGlobalMouseMove)
  window.removeEventListener('mouseup', stopSeek)
  if (videoRef.value) videoRef.value.pause()
})
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.8);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  animation: fadeIn 0.3s ease;
}

.modal-content {
  background: var(--panel);
  border-radius: 18px;
  border: 1px solid var(--border);
  width: min(1120px, 94vw);
  max-height: 92vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  animation: slideIn 0.3s ease;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3);
}

.modal-content.is-expanded {
  width: min(1800px, 98vw);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  padding: 18px 24px;
  border-bottom: 1px solid var(--border);
  background: var(--panel-alt);
}

.modal-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  color: var(--text);
}

.modal-header__actions {
  display: inline-flex;
  align-items: center;
  gap: 10px;
}

.modal-subtitle {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--muted);
}

.close-btn {
  background: none;
  border: none;
  color: var(--muted);
  font-size: 24px;
  cursor: pointer;
  padding: 0;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  transition: all 0.2s var(--ease-out);
}

.expand-btn {
  padding: 8px 12px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--panel);
  color: var(--text);
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  transition:
    background .2s var(--ease-out),
    border-color .2s var(--ease-out),
    transform .2s var(--ease-out);
}

.expand-btn:hover {
  transform: translateY(-1px);
  background: var(--nav-hover);
  border-color: color-mix(in srgb, var(--accent) 35%, var(--border));
}

.close-btn:hover {
  background: rgba(255, 255, 255, 0.08);
  color: var(--text);
}

.close-icon {
  line-height: 1;
}

.modal-body {
  flex: 1;
  padding: 24px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.loading {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 360px;
  color: var(--muted);
  font-size: 16px;
}

.modal-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(320px, 0.85fr);
  gap: 20px;
  align-items: start;
}

.modal-content.is-expanded .modal-layout {
  grid-template-columns: 1fr;
}

.modal-content.is-expanded .side-panel {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  align-items: start;
}

.player-panel,
.side-panel {
  min-width: 0;
}

.side-panel {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.video-card {
  border: 1px solid var(--border);
  border-radius: 16px;
  background: linear-gradient(180deg, rgba(255,255,255,.02), rgba(255,255,255,.01));
  overflow: hidden;
}

.video-container {
  position: relative;
  width: 100%;
  min-height: 0;
  background: #02040a;
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 14px;
}

.video-player {
  display: block;
  width: 100%;
  height: auto;
  max-height: min(66vh, 720px);
  border: none;
  border-radius: 12px;
  background: #02040a;
  object-fit: contain;
}

.modal-content.is-expanded .video-player {
  max-height: min(78vh, 980px);
}

.player-shell {
  padding: 30px 18px 18px;
  background: var(--panel-alt);
}

.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 26px;
}

.marker-title {
  font-size: 11px;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: .12em;
  color: var(--muted);
}

.marker-hint {
  font-size: 12px;
  color: var(--muted);
}

.progress-track {
  position: relative;
  border-radius: 999px;
}

.progress-track.disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.marker-bug {
  position: absolute;
  top: -18px;
  transform: translateX(-50%);
  border: none;
  background: transparent;
  cursor: pointer;
  padding: 0;
  font-size: 17px;
  line-height: 1;
  filter: drop-shadow(0 4px 8px rgba(0, 0, 0, 0.35));
}

.marker-bug--a {
  filter: drop-shadow(0 0 4px #38bdf8) drop-shadow(0 4px 8px rgba(0, 0, 0, 0.4));
}
.marker-bug--b {
  filter: drop-shadow(0 0 4px #f472b6) drop-shadow(0 4px 8px rgba(0, 0, 0, 0.4));
}
.marker-bug--both {
  filter: drop-shadow(0 0 4px #facc15) drop-shadow(0 4px 8px rgba(0, 0, 0, 0.4));
}

.progress-track {
  height: 12px;
  background: rgba(255, 255, 255, 0.08);
  overflow: visible;
  cursor: pointer;
  margin-top: 2px;
}

.progress-fill {
  position: absolute;
  inset: 0 auto 0 0;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, var(--accent), var(--accent-2));
}

.progress-thumb {
  position: absolute;
  top: 50%;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #f8fbff;
  border: 2px solid var(--accent);
  transform: translate(-50%, -50%);
  box-shadow: 0 10px 18px rgba(0, 0, 0, 0.24);
}

.player-controls {
  margin-top: 14px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.time-readout {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 700;
  color: var(--text);
}

.control-buttons {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.player-btn,
.btn-close,
.btn-save {
  padding: 10px 16px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--panel);
  color: var(--text);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition:
    background .2s var(--ease-out),
    transform .2s var(--ease-out),
    border-color .2s var(--ease-out);
}

.player-btn:hover,
.btn-close:hover,
.btn-save:hover {
  transform: translateY(-1px);
}

.player-btn.primary,
.btn-save {
  background: linear-gradient(180deg, var(--accent), #6ec8f4);
  color: var(--primary-btn-text, #0a0d16);
  border-color: rgba(125, 211, 252, 0.36);
}

.player-btn.bug-btn {
  background: linear-gradient(180deg, rgba(248, 113, 113, 0.92), rgba(239, 68, 68, 0.82));
  border-color: rgba(248, 113, 113, 0.42);
  color: #fff7f7;
}

.side-picker {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--panel);
}
.side-picker__label {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: var(--muted);
}
.side-picker__btn {
  border: 1px solid transparent;
  background: transparent;
  color: var(--muted);
  font-size: 11px;
  font-weight: 700;
  padding: 3px 8px;
  border-radius: 8px;
  cursor: pointer;
  transition: background .15s var(--ease-out), color .15s var(--ease-out), border-color .15s var(--ease-out);
}
.side-picker__btn:hover { color: var(--text); background: var(--nav-hover); }
.side-picker__btn--a.active   { color: #0a0d16; background: #38bdf8; border-color: #38bdf8; }
.side-picker__btn--b.active   { color: #0a0d16; background: #f472b6; border-color: #f472b6; }
.side-picker__btn--both.active{ color: #0a0d16; background: #facc15; border-color: #facc15; }

.ab-tag {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 24px;
  padding: 0 6px;
  height: 18px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: .04em;
  border: 1px solid transparent;
  color: #0a0d16;
}
.ab-tag--a    { background: #38bdf8; }
.ab-tag--b    { background: #f472b6; }
.ab-tag--both { background: #facc15; }

.info-row--ab .info-label { display: inline-flex; align-items: center; gap: 6px; }
.info-value.mono {
  font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
  font-size: 12px;
  color: var(--text);
  word-break: break-all;
}

.player-btn:disabled,
.btn-save:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
}

.review-panel {
  position: relative;
  background:
    radial-gradient(420px 180px at 0% 0%, color-mix(in srgb, var(--accent) 12%, transparent), transparent 60%),
    var(--panel-alt);
  padding: 16px;
  border-radius: 16px;
  border: 1px solid var(--border);
  overflow: hidden;
}

.review-panel__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 4px;
}

.verdict-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px 4px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  border: 1px solid var(--border);
  color: var(--muted);
  background: color-mix(in srgb, var(--panel) 70%, transparent);
}

.verdict-pill__dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: currentColor;
  box-shadow: 0 0 8px currentColor;
}

.verdict-pill.is-issue {
  color: #f87171;
  border-color: rgba(248, 113, 113, 0.4);
  background: rgba(248, 113, 113, 0.10);
}
.verdict-pill.is-clean {
  color: #4ade80;
  border-color: rgba(74, 222, 128, 0.4);
  background: rgba(74, 222, 128, 0.10);
}
.verdict-pill.is-pending {
  color: #cbd5e1;
  border-color: rgba(148, 163, 184, 0.32);
  background: rgba(148, 163, 184, 0.08);
}

.review-hint {
  margin: 6px 0 14px;
  font-size: 12px;
  color: var(--muted);
}

.review-actions {
  display: flex;
  gap: 6px;
  margin-bottom: 12px;
  padding: 4px;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: color-mix(in srgb, var(--panel) 60%, transparent);
}

.review-btn {
  flex: 1 1 0;
  min-width: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 9px 10px;
  border-radius: 9px;
  border: 0;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: .02em;
  cursor: pointer;
  background: transparent;
  color: var(--muted);
  transition:
    background .18s var(--ease-out),
    color .18s var(--ease-out),
    transform .18s var(--ease-out),
    box-shadow .18s var(--ease-out);
}

.review-btn__icon {
  font-size: 13px;
  line-height: 1;
  opacity: .9;
}

.review-btn:hover:not(:disabled):not(.active) {
  background: var(--nav-hover);
  color: var(--text);
}

.review-btn.issue.active {
  color: #f87171;
  background: linear-gradient(180deg, rgba(248, 113, 113, 0.22), rgba(248, 113, 113, 0.10));
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.10),
    0 6px 16px rgba(248, 113, 113, 0.20);
}

.review-btn.clean.active {
  color: #4ade80;
  background: linear-gradient(180deg, rgba(74, 222, 128, 0.22), rgba(74, 222, 128, 0.10));
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.10),
    0 6px 16px rgba(74, 222, 128, 0.20);
}

.review-btn.reset.active {
  color: var(--text);
  background: var(--nav-hover);
}

.review-btn:not(.active):active { transform: scale(.98); }

.review-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.review-note {
  width: 100%;
  min-height: 78px;
  resize: vertical;
  padding: 11px 13px;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: color-mix(in srgb, var(--panel) 80%, transparent);
  color: var(--text);
  font-family: inherit;
  font-size: 13px;
  line-height: 1.5;
  margin-bottom: 10px;
  transition:
    border-color .2s var(--ease-out),
    background .2s var(--ease-out),
    box-shadow .2s var(--ease-out);
}

.review-note:focus {
  outline: none;
  border-color: color-mix(in srgb, var(--accent) 55%, var(--border));
  box-shadow: 0 0 0 4px color-mix(in srgb, var(--accent) 18%, transparent);
}

.btn-save-review {
  padding: 9px 14px;
  border-radius: 11px;
  border: 1px solid var(--border);
  background: color-mix(in srgb, var(--panel) 70%, transparent);
  color: var(--text);
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  margin-bottom: 8px;
  transition:
    background .18s var(--ease-out),
    border-color .18s var(--ease-out),
    transform .18s var(--ease-out);
}

.btn-save-review:hover:not(:disabled) {
  background: var(--nav-hover);
  border-color: color-mix(in srgb, var(--accent) 35%, var(--border));
  transform: translateY(-1px);
}

.btn-save-review:active:not(:disabled) { transform: scale(.98); }

.btn-save-review:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.review-status {
  display: block;
  font-size: 12px;
  margin-top: 4px;
}

.review-status.subtle {
  color: var(--muted);
}

.review-status.error {
  color: var(--danger);
}

.video-info,
.annotation-panel {
  background: var(--panel-alt);
  padding: 16px;
  border-radius: 14px;
  border: 1px solid var(--border);
}

.section-title {
  font-size: 12px;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: .12em;
  color: var(--muted);
  margin-bottom: 12px;
}

.info-row {
  display: flex;
  justify-content: space-between;
  margin-bottom: 10px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--border);
  gap: 12px;
}

.info-row:last-child {
  margin-bottom: 0;
  padding-bottom: 0;
  border-bottom: none;
}

.info-label {
  font-size: 13px;
  color: var(--muted);
  font-weight: 600;
}

.info-value {
  font-size: 13px;
  color: var(--text);
  font-weight: 700;
  text-align: right;
  flex: 1;
  word-break: break-all;
}

.annotation-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
  margin-bottom: 12px;
}

.annotation-hint {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--muted);
}

.annotation-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(125, 211, 252, 0.1);
  color: var(--accent);
  border: 1px solid rgba(125, 211, 252, 0.2);
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
}

.note-input {
  width: 100%;
  min-height: 124px;
  resize: vertical;
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: var(--panel);
  color: var(--text);
  font-family: inherit;
  font-size: 13px;
  line-height: 1.6;
}

.marker-list {
  margin-top: 14px;
}

.marker-list__title {
  font-size: 12px;
  font-weight: 700;
  color: var(--text);
  margin-bottom: 10px;
}

.marker-items {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.marker-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: rgba(255, 255, 255, 0.02);
}

.marker-jump,
.marker-delete {
  border: none;
  background: transparent;
  cursor: pointer;
  padding: 0;
  font-size: 13px;
}

.marker-jump {
  color: var(--text);
  font-weight: 700;
}

.marker-delete {
  color: var(--danger);
  font-weight: 700;
}

.marker-empty {
  font-size: 12px;
  color: var(--muted);
  padding: 12px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px dashed var(--border);
}

.annotation-actions {
  margin-top: 14px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.save-status {
  font-size: 12px;
  color: var(--muted);
}

.save-status.saved {
  color: var(--success);
}

.save-status.error {
  color: var(--danger);
}

.modal-footer {
  padding: 16px 24px;
  border-top: 1px solid var(--border);
  background: var(--panel-alt);
  display: flex;
  justify-content: flex-end;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (max-width: 900px) {
  .modal-layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .modal-content {
    width: 95%;
    max-height: 95vh;
  }

  .modal-header,
  .modal-footer {
    padding: 12px 16px;
  }

  .modal-body {
    padding: 16px;
  }

  .video-container {
    padding: 10px;
  }

  .video-container {
    min-height: 0;
  }

  .player-controls,
  .annotation-actions,
  .progress-header {
    flex-direction: column;
    align-items: stretch;
  }

  .control-buttons {
    width: 100%;
  }

  .player-btn {
    flex: 1 1 calc(50% - 8px);
  }
}

.modal-body::-webkit-scrollbar {
  width: 8px;
}

.modal-body::-webkit-scrollbar-track {
  background: var(--panel);
  border-radius: 4px;
}

.modal-body::-webkit-scrollbar-thumb {
  background: var(--border);
  border-radius: 4px;
}

.modal-body::-webkit-scrollbar-thumb:hover {
  background: var(--muted);
}
</style>