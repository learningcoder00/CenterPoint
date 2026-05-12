<template>
  <section class="dash">
    <div class="dash-head">
      <div>
        <div class="section-kicker">Review snapshot</div>
        <h2>Verdict distribution & top signals</h2>
      </div>
      <span class="dash-meta">{{ completed.length }} completed job<span v-if="completed.length !== 1">s</span></span>
    </div>

    <div class="dash-grid">
      <article class="dash-card">
        <div class="dash-card__label">Verdict mix</div>
        <div v-if="!completed.length" class="dash-empty">No completed jobs yet.</div>
        <template v-else>
          <div class="verdict-bar" role="img" :aria-label="verdictAria">
            <div
              v-for="seg in verdictSegments"
              :key="seg.key"
              :class="['verdict-seg', `verdict-seg--${seg.key}`]"
              :style="{ width: seg.pct + '%' }"
              :title="`${seg.label}: ${seg.count} (${seg.pct.toFixed(0)}%)`"
            ></div>
          </div>
          <ul class="verdict-legend">
            <li v-for="seg in verdictSegments" :key="seg.key">
              <span :class="['legend-dot', `legend-dot--${seg.key}`]"></span>
              <span class="legend-label">{{ seg.label }}</span>
              <span class="legend-count">{{ seg.count }}</span>
              <span class="legend-pct">{{ seg.pct.toFixed(0) }}%</span>
            </li>
          </ul>
        </template>
      </article>

      <article class="dash-card">
        <div class="dash-card__label">Top tags on flagged clips</div>
        <div v-if="!topTags.length" class="dash-empty">
          No tagged clips with the current filter.
        </div>
        <ul v-else class="tag-bars">
          <li v-for="t in topTags" :key="t.tag" class="tag-row">
            <span class="tag-name" :title="t.tag">{{ t.tag }}</span>
            <div class="tag-track">
              <div class="tag-fill" :style="{ width: barWidth(t.count) + '%' }"></div>
            </div>
            <span class="tag-count">{{ t.count }}</span>
          </li>
        </ul>
      </article>

      <article class="dash-card">
        <div class="dash-card__label">Last 7 days · completed jobs</div>
        <div v-if="!last7Days.some(d => d.count > 0)" class="dash-empty">
          No jobs completed in the past week.
        </div>
        <div v-else class="spark">
          <div
            v-for="day in last7Days"
            :key="day.iso"
            class="spark-col"
            :title="`${day.label}: ${day.count} job${day.count === 1 ? '' : 's'}`"
          >
            <div class="spark-bar" :style="{ height: sparkHeight(day.count) + '%' }"></div>
            <span class="spark-label">{{ day.short }}</span>
          </div>
        </div>
      </article>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  jobs: { type: Array, default: () => [] },
  clipsTags: { type: Object, default: () => ({}) },
})

const completed = computed(() =>
  (props.jobs || []).filter(j => j.status === 'completed' && j.visualization_mode !== 'bev_compare')
)

const verdictCounts = computed(() => {
  const counts = { issues: 0, clean: 0, pending: 0 }
  for (const j of completed.value) {
    if (j.review_status === 'has_issue') counts.issues += 1
    else if (j.review_status === 'no_issue') counts.clean += 1
    else counts.pending += 1
  }
  return counts
})

const verdictSegments = computed(() => {
  const total = completed.value.length || 1
  const c = verdictCounts.value
  return [
    { key: 'issues', label: 'Issues', count: c.issues, pct: (c.issues / total) * 100 },
    { key: 'clean', label: 'Clean', count: c.clean, pct: (c.clean / total) * 100 },
    { key: 'pending', label: 'Pending', count: c.pending, pct: (c.pending / total) * 100 },
  ]
})

const verdictAria = computed(() => {
  const c = verdictCounts.value
  return `Issues ${c.issues}, Clean ${c.clean}, Pending ${c.pending}`
})

const topTags = computed(() => {
  const map = new Map()
  for (const j of completed.value) {
    if (j.review_status !== 'has_issue') continue
    const tags = props.clipsTags[j.clip_id] || []
    for (const tag of tags) {
      if (!tag) continue
      map.set(tag, (map.get(tag) || 0) + 1)
    }
  }
  return [...map.entries()]
    .map(([tag, count]) => ({ tag, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 6)
})

const maxTagCount = computed(() => topTags.value.reduce((m, t) => Math.max(m, t.count), 1))

function barWidth(count) {
  return (count / maxTagCount.value) * 100
}

const last7Days = computed(() => {
  const days = []
  const now = new Date()
  for (let i = 6; i >= 0; i--) {
    const d = new Date(now)
    d.setHours(0, 0, 0, 0)
    d.setDate(d.getDate() - i)
    const iso = d.toISOString().slice(0, 10)
    days.push({
      iso,
      label: d.toLocaleDateString(),
      short: d.toLocaleDateString(undefined, { weekday: 'short' }),
      start: d.getTime() / 1000,
      end: (d.getTime() + 86_400_000) / 1000,
      count: 0,
    })
  }
  for (const j of completed.value) {
    const ts = Number(j.updated_at || j.created_at || 0)
    if (!ts) continue
    const tsSec = ts < 1e12 ? ts : ts / 1000
    const day = days.find((d) => tsSec >= d.start && tsSec < d.end)
    if (day) day.count += 1
  }
  return days
})

const maxDayCount = computed(() => Math.max(1, ...last7Days.value.map(d => d.count)))

function sparkHeight(count) {
  if (!count) return 4
  return 10 + (count / maxDayCount.value) * 90
}
</script>

<style scoped>
.dash {
  background:
    radial-gradient(420px 220px at 100% 0%, color-mix(in srgb, var(--accent) 12%, transparent), transparent 60%),
    var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 18px;
  padding: 18px 18px 16px;
  margin-bottom: 18px;
  box-shadow: var(--shadow);
}

.dash-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.dash-head h2 {
  margin: 4px 0 0;
  font-size: 17px;
  font-weight: 800;
  letter-spacing: -0.01em;
}

.dash-meta {
  font-size: 12px;
  color: var(--muted);
  font-weight: 700;
  letter-spacing: .04em;
}

.section-kicker {
  color: var(--accent);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: .14em;
  font-weight: 800;
}

.dash-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(0, 1fr) minmax(0, 1fr);
  gap: 14px;
}

.dash-card {
  padding: 14px;
  border: 1px solid var(--border);
  border-radius: 14px;
  background: var(--panel-alt);
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 132px;
}

.dash-card__label {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: .12em;
  color: var(--muted);
  font-weight: 800;
}

.dash-empty {
  color: var(--muted);
  font-size: 12px;
  padding: 14px 0;
  text-align: center;
}

.verdict-bar {
  position: relative;
  display: flex;
  height: 14px;
  border-radius: 999px;
  overflow: hidden;
  background: color-mix(in srgb, var(--muted) 18%, transparent);
}

.verdict-seg {
  height: 100%;
  transition: width .4s var(--ease-out);
}

.verdict-seg--issues { background: linear-gradient(90deg, #f87171, #fb7185); }
.verdict-seg--clean { background: linear-gradient(90deg, #4ade80, #22d3ee); }
.verdict-seg--pending { background: linear-gradient(90deg, #94a3b8, #cbd5e1); }

.verdict-legend {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 6px 14px;
}

.verdict-legend li {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
}

.legend-dot {
  width: 9px;
  height: 9px;
  border-radius: 999px;
}

.legend-dot--issues { background: #f87171; }
.legend-dot--clean { background: #4ade80; }
.legend-dot--pending { background: #94a3b8; }

.legend-label {
  color: var(--text);
  font-weight: 700;
}

.legend-count {
  color: var(--text);
  font-variant-numeric: tabular-nums;
  font-weight: 700;
}

.legend-pct {
  color: var(--muted);
  font-size: 11px;
}

.tag-bars {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.tag-row {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) minmax(60px, 3fr) 32px;
  gap: 8px;
  align-items: center;
  font-size: 12px;
}

.tag-name {
  color: var(--text);
  font-weight: 700;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tag-track {
  height: 8px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--muted) 18%, transparent);
  overflow: hidden;
}

.tag-fill {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #f87171, #fbbf24);
}

.tag-count {
  text-align: right;
  font-variant-numeric: tabular-nums;
  color: var(--text);
  font-weight: 700;
}

.spark {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 8px;
  align-items: end;
  min-height: 84px;
}

.spark-col {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  height: 100%;
}

.spark-bar {
  width: 100%;
  background: linear-gradient(180deg, color-mix(in srgb, var(--accent) 85%, transparent), color-mix(in srgb, var(--accent) 28%, transparent));
  border-radius: 6px 6px 0 0;
  min-height: 4px;
  transition: height .4s var(--ease-out);
}

.spark-label {
  font-size: 10px;
  color: var(--muted);
  font-weight: 700;
  letter-spacing: .04em;
}

@media (max-width: 1024px) {
  .dash-grid { grid-template-columns: 1fr; }
}
</style>
