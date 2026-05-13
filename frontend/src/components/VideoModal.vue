<template>
  <div v-if="visible" class="modal-overlay" @click="$emit('close')">
    <div class="modal-content" @click.stop>
      <div class="modal-header">
        <div>
          <h3>Video Playback</h3>
          <p v-if="job" class="modal-subtitle">{{ job.clip_id }} · {{ job.job_id }}</p>
        </div>
        <div class="modal-header__actions">
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
                  <button
                    type="button"
                    class="fs-btn"
                    :class="{ 'is-on': isFullscreen }"
                    :disabled="!videoSrc"
                    :title="isFullscreen ? 'Exit fullscreen' : 'Fullscreen video'"
                    :aria-label="isFullscreen ? 'Exit fullscreen' : 'Fullscreen video'"
                    @click="toggleFullscreen"
                  >
                    <svg v-if="!isFullscreen" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                      <path d="M4 9V5a1 1 0 0 1 1-1h4" />
                      <path d="M20 9V5a1 1 0 0 0-1-1h-4" />
                      <path d="M4 15v4a1 1 0 0 0 1 1h4" />
                      <path d="M20 15v4a1 1 0 0 1-1 1h-4" />
                    </svg>
                    <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                      <path d="M9 4v4a1 1 0 0 1-1 1H4" />
                      <path d="M15 4v4a1 1 0 0 0 1 1h4" />
                      <path d="M9 20v-4a1 1 0 0 0-1-1H4" />
                      <path d="M15 20v-4a1 1 0 0 1 1-1h4" />
                    </svg>
                  </button>
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
                      <button type="button" class="player-btn" :disabled="!duration" title="Previous frame" @click="stepFrames(-1)">⏮ Frame</button>
                      <button type="button" class="player-btn" :disabled="!duration" title="Seek -1s (←)" @click="seekBy(-1)">-1s</button>
                      <button type="button" class="player-btn primary" :disabled="!videoSrc" title="Play / pause (Space)" @click="togglePlay">
                        {{ isPlaying ? 'Pause' : 'Play' }}
                      </button>
                      <button type="button" class="player-btn" :disabled="!duration" title="Seek +1s (→)" @click="seekBy(1)">+1s</button>
                      <button type="button" class="player-btn" :disabled="!duration" title="Next frame" @click="stepFrames(1)">Frame ⏭</button>
                      <button type="button" class="player-btn bug-btn" :disabled="!duration" title="Add bug at current time (B)" @click="addMarkerAtCurrentTime">
                        🐞 Add bug (B)
                      </button>
                    </div>
                  </div>

                  <div class="keymap-row">
                    <span class="keymap-hint">Shortcuts:</span>
                    <span class="kbd">Space</span><span class="kbd-label">play</span>
                    <span class="kbd">←</span><span class="kbd-label">-1s</span>
                    <span class="kbd">→</span><span class="kbd-label">+1s</span>
                    <span class="kbd">B</span><span class="kbd-label">add bug</span>
                    <span class="kbd">Esc</span><span class="kbd-label">close</span>
                  </div>
                </div>
              </div>
            </div>

            <div class="side-panel">
              <div v-if="job?.status === 'completed' && !isCompareJob" class="review-panel">
                <div class="review-panel__head">
                  <div class="review-title-block">
                    <div class="section-title review-title">Review verdict</div>
                    <p class="review-hint">Mark this visualization job for triage lists.</p>
                  </div>
                  <span :class="['verdict-pill', currentVerdictClass]" aria-live="polite">
                    <span class="verdict-pill__dot"></span>
                    {{ reviewStatusLabel }}
                  </span>
                </div>
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
                <div class="review-cta-row">
                  <button
                    type="button"
                    class="btn-save-review"
                    :disabled="reviewSaving || reviewLoading || !reviewDirty"
                    @click="saveReviewNoteOnly"
                  >
                    {{ reviewSaving ? 'Saving…' : 'Save verdict note' }}
                  </button>
                  <button
                    type="button"
                    class="btn-ask-ai"
                    :disabled="!job?.job_id || job?.status !== 'completed'"
                    title="Open AI Optimization with this job pre-filled"
                    @click="askAiForJob"
                  >
                    <span class="ask-ai-icon">✨</span>
                    Ask AI
                  </button>
                </div>
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
                <button
                  type="button"
                  class="btn-export-json"
                  :disabled="annotationLoading || !job?.job_id"
                  title="Download note + markers + verdict as JSON"
                  @click="exportAnnotationsJson"
                >
                  ⬇ Export JSON
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
import { useRouter } from 'vue-router'
import { downloadFile, fmtStatus, fmtTime } from '../utils.js'
import { fetchJobAnnotations, saveJobAnnotations, videoUrl, fetchJobReview, setJobReview } from '../api.js'

const props = defineProps({
  visible: Boolean,
  job: Object,
})

const emit = defineEmits(['close', 'review-updated'])

const router = useRouter()

function exportAnnotationsJson() {
  if (!props.job?.job_id) return
  const payload = {
    job_id: props.job.job_id,
    clip_id: props.job.clip_id,
    visualization_mode: props.job.visualization_mode,
    status: props.job.status,
    review: {
      status: reviewStatus.value || 'unreviewed',
      reviewer_note: reviewerNote.value || '',
    },
    annotations: {
      note: noteText.value || '',
      markers: sortedMarkers.value.map((m) => ({
        id: m.id,
        time_sec: m.timeSec,
        type: m.type,
        side: m.side,
      })),
    },
    exported_at: new Date().toISOString(),
  }
  const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')
  downloadFile(
    JSON.stringify(payload, null, 2),
    `centerpoint-annotations-${props.job.job_id}-${stamp}.json`,
    'application/json;charset=utf-8'
  )
}

function askAiForJob() {
  const jobId = props.job?.job_id
  if (!jobId) return
  const query = { jobId }
  const description = [reviewerNote.value, noteText.value]
    .map((s) => (s || '').trim())
    .filter(Boolean)
    .join('\n\n')
  if (description) query.description = description
  emit('close')
  router.push({ path: '/ai-optimization', query })
}

const videoRef = ref(null)
const progressTrackRef = ref(null)

const currentTime = ref(0)
const duration = ref(0)
const isPlaying = ref(false)
const isSeeking = ref(false)
const dragRatio = ref(0)
const wasPlayingBeforeSeek = ref(false)
const isFullscreen = ref(false)

const noteText = ref('')
const markers = ref([])
const annotationLoading = ref(false)
const annotationSaving = ref(false)
const saveState = ref('idle')

/**
 * Stitched BEV/Cameras videos are encoded at ~10 fps (see start_server stitching).
 * Used by , / . frame stepping so each press moves a perceptible step regardless
 * of how the underlying browser reports `requestVideoFrameCallback` precision.
 */
const ASSUMED_FPS = 10

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
  if (!jobId || props.job?.status !== 'completed' || isCompareJob.value) return
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

/**
 * Step the video by N frames using the configured FPS hint (default 10 fps for
 * stitched BEV videos). Always pauses first to keep the step visible.
 */
function stepFrames(steps) {
  if (!videoRef.value || !duration.value) return
  if (!videoRef.value.paused) videoRef.value.pause()
  const fps = ASSUMED_FPS
  seekToTime(currentTime.value + steps / fps)
}

function togglePlay() {
  if (!videoRef.value) return
  if (videoRef.value.paused) {
    videoRef.value.play().catch((e) => console.log('Video play failed:', e))
  } else {
    videoRef.value.pause()
  }
}

/**
 * Browser fullscreen for the <video> element. We deliberately target the
 * video itself (not the modal container) so the OS gives the user the full
 * native player surface; native controls are toggled on while in FS so play
 * / seek / volume remain reachable without our custom toolbar.
 */
async function toggleFullscreen() {
  const v = videoRef.value
  if (!v) return
  try {
    if (!isFullscreen.value) {
      const req = v.requestFullscreen || v.webkitRequestFullscreen || v.webkitEnterFullscreen || v.msRequestFullscreen
      if (req) await req.call(v)
    } else {
      const exit = document.exitFullscreen || document.webkitExitFullscreen || document.msExitFullscreen
      if (exit) await exit.call(document)
    }
  } catch (e) {
    console.warn('Fullscreen toggle failed:', e)
  }
}

function onFullscreenChange() {
  const fsEl = document.fullscreenElement || document.webkitFullscreenElement || document.msFullscreenElement
  isFullscreen.value = !!fsEl && fsEl === videoRef.value
  if (videoRef.value) {
    if (isFullscreen.value) {
      videoRef.value.setAttribute('controls', '')
    } else {
      videoRef.value.removeAttribute('controls')
    }
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
      side: 'both',
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

/** Bail out of fullscreen — used before the modal closes / unmounts. */
function exitFullscreenIfActive() {
  const fsEl = document.fullscreenElement || document.webkitFullscreenElement || document.msFullscreenElement
  if (!fsEl) return
  try {
    const exit = document.exitFullscreen || document.webkitExitFullscreen || document.msExitFullscreen
    if (exit) exit.call(document)
  } catch { /* ignore */ }
}

function resetAnnotationState() {
  noteText.value = ''
  markers.value = []
  annotationLoading.value = false
  annotationSaving.value = false
  saveState.value = 'idle'
}

function resetReviewState() {
  reviewStatus.value = 'unreviewed'
  reviewerNote.value = ''
  reviewLoading.value = false
  reviewSaving.value = false
  reviewError.value = ''
  reviewDirty.value = false
}

function isTypingTarget(e) {
  const t = e.target
  if (!t) return false
  if (t.isContentEditable) return true
  const tag = (t.tagName || '').toLowerCase()
  return tag === 'input' || tag === 'textarea' || tag === 'select'
}

function onKeydown(e) {
  if (!props.visible) return
  if (e.key === 'Escape') {
    emit('close')
    return
  }
  if (isTypingTarget(e)) return
  // Modifier keys disable shortcuts so browser/system combos (Ctrl+R, etc.) still work.
  if (e.metaKey || e.ctrlKey || e.altKey || e.shiftKey) return

  switch (e.key) {
    case ' ': // Space → play/pause
      togglePlay()
      e.preventDefault()
      break
    case 'ArrowLeft': // ← → seek -1s
      seekBy(-1)
      e.preventDefault()
      break
    case 'ArrowRight': // → → seek +1s
      seekBy(1)
      e.preventDefault()
      break
    case 'b':
    case 'B':
      addMarkerAtCurrentTime()
      e.preventDefault()
      break
    default:
      break
  }
}

watch(
  () => [props.visible, props.job?.job_id],
  async ([visible]) => {
    if (!visible) {
      exitFullscreenIfActive()
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
  document.addEventListener('fullscreenchange', onFullscreenChange)
  document.addEventListener('webkitfullscreenchange', onFullscreenChange)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
  window.removeEventListener('mousemove', onGlobalMouseMove)
  window.removeEventListener('mouseup', stopSeek)
  document.removeEventListener('fullscreenchange', onFullscreenChange)
  document.removeEventListener('webkitfullscreenchange', onFullscreenChange)
  exitFullscreenIfActive()
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

/* Fullscreen video uses the browser's native player size; reset our max-height
   constraint so the OS gives us the entire viewport. */
.video-player:fullscreen,
.video-player:-webkit-full-screen {
  max-height: none;
  width: 100%;
  height: 100%;
  border-radius: 0;
  background: #000;
}

.fs-btn {
  position: absolute;
  top: 22px;
  right: 22px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.18);
  background: rgba(10, 13, 22, 0.55);
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
  color: #f0f6ff;
  cursor: pointer;
  opacity: 0;
  transform: translateY(-2px);
  transition:
    opacity .18s var(--ease-out),
    transform .18s var(--ease-out),
    background .18s var(--ease-out),
    border-color .18s var(--ease-out);
  z-index: 2;
}

.video-container:hover .fs-btn,
.fs-btn:focus-visible,
.fs-btn.is-on {
  opacity: 1;
  transform: translateY(0);
}

.fs-btn:hover {
  background: rgba(56, 189, 248, 0.22);
  border-color: rgba(125, 211, 252, 0.55);
  color: #e0f2fe;
}

.fs-btn:active {
  transform: translateY(0) scale(0.96);
}

.fs-btn:disabled {
  opacity: 0;
  cursor: not-allowed;
}

.fs-btn.is-on {
  background: rgba(125, 211, 252, 0.32);
  border-color: rgba(125, 211, 252, 0.7);
  color: #e0f2fe;
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

.player-btn.primary {
  min-width: 88px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-variant-numeric: tabular-nums;
}

.player-btn.bug-btn {
  background: linear-gradient(180deg, rgba(248, 113, 113, 0.92), rgba(239, 68, 68, 0.82));
  border-color: rgba(248, 113, 113, 0.42);
  color: #fff7f7;
}

.btn-export-json {
  padding: 10px 14px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--panel);
  color: var(--text);
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  transition: background .18s var(--ease-out), border-color .18s var(--ease-out);
}

.btn-export-json:hover:not(:disabled) {
  background: var(--panel-alt);
  border-color: var(--accent);
}

.btn-export-json:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.keymap-row {
  margin-top: 14px;
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px dashed var(--border);
  background: color-mix(in srgb, var(--panel) 70%, transparent);
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px 8px;
  font-size: 11px;
  color: var(--muted);
}

.keymap-hint {
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: .12em;
  color: var(--muted);
  margin-right: 4px;
}

.kbd {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 2px 6px;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: var(--panel-alt);
  color: var(--text);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 11px;
  font-weight: 700;
  box-shadow: inset 0 -1px 0 rgba(0, 0, 0, 0.18);
}

.kbd-label {
  margin-right: 8px;
  letter-spacing: .04em;
}

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
    radial-gradient(360px 180px at 0% 0%, color-mix(in srgb, var(--accent) 14%, transparent), transparent 62%),
    linear-gradient(180deg, color-mix(in srgb, #ffffff 4%, transparent), transparent 36%),
    var(--panel-alt);
  padding: 18px;
  border-radius: 18px;
  border: 1px solid color-mix(in srgb, var(--accent) 18%, var(--border));
  overflow: hidden;
}

.review-panel::before {
  content: '';
  position: absolute;
  inset: 0 0 auto;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(125, 211, 252, 0.46), transparent);
  pointer-events: none;
}

.review-panel__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 14px;
}

.review-title-block {
  min-width: 0;
}

.review-panel .review-title {
  margin-bottom: 5px;
  color: var(--text);
  letter-spacing: .14em;
}

.verdict-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex: 0 0 auto;
  padding: 5px 11px 5px 9px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  border: 1px solid var(--border);
  color: var(--muted);
  background: color-mix(in srgb, var(--panel) 70%, transparent);
}

.verdict-pill__dot {
  width: 6px;
  height: 6px;
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
  margin: 0;
  font-size: 12px;
  color: var(--muted);
  line-height: 1.45;
}

.review-actions {
  display: flex;
  gap: 6px;
  margin-bottom: 14px;
  padding: 5px;
  border: 1px solid var(--border);
  border-radius: 14px;
  background: color-mix(in srgb, var(--panel) 68%, transparent);
}

.review-btn {
  flex: 1 1 0;
  min-width: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-height: 34px;
  padding: 8px 10px;
  border-radius: 10px;
  border: 0;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: .03em;
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
  min-height: 84px;
  resize: vertical;
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid var(--border);
  background: color-mix(in srgb, var(--panel) 84%, transparent);
  color: var(--text);
  font-family: inherit;
  font-size: 13px;
  line-height: 1.5;
  margin-bottom: 12px;
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
  min-height: 36px;
  padding: 0 14px;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: color-mix(in srgb, var(--panel) 70%, transparent);
  color: var(--text);
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  margin-bottom: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
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

.review-cta-row {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.btn-ask-ai {
  min-height: 36px;
  padding: 0 14px;
  border-radius: 12px;
  border: 1px solid rgba(192, 132, 252, 0.4);
  background: linear-gradient(180deg, rgba(192, 132, 252, 0.22), rgba(192, 132, 252, 0.10));
  color: #ede9fe;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: .02em;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  transition:
    background .18s var(--ease-out),
    border-color .18s var(--ease-out),
    transform .18s var(--ease-out);
}

.btn-ask-ai:hover:not(:disabled) {
  background: linear-gradient(180deg, rgba(192, 132, 252, 0.32), rgba(192, 132, 252, 0.16));
  border-color: rgba(192, 132, 252, 0.65);
  transform: translateY(-1px);
}

.btn-ask-ai:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.ask-ai-icon {
  font-size: 13px;
}

.review-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  min-height: 20px;
  padding-top: 2px;
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