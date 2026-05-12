export function fmtDuration(s) {
  return `${s.toFixed(1)}s`
}

/** Backend stores Unix time as seconds; JS Date expects ms. Values >= 1e12 are treated as ms. */
export function fmtTime(ts) {
  if (ts == null || ts === '') return '—'
  const n = Number(ts)
  if (!Number.isFinite(n)) return '—'
  const ms = n < 1e12 ? n * 1000 : n
  return new Date(ms).toLocaleString()
}

export function fmtStatus(s) {
  const map = {
    pending: 'Pending',
    running: 'Running',
    stitching: 'Stitching',
    completed: 'Completed',
    failed: 'Failed',
    cancelled: 'Cancelled',
  }
  return map[s] || s
}

export function fmtPath(p) {
  if (!p) return '—'
  const parts = p.replace(/\\/g, '/').split('/')
  return parts.length > 2 ? '…/' + parts.slice(-2).join('/') : p
}

/** Trigger a browser download of the given Blob/string content. */
export function downloadFile(content, filename, mimeType = 'application/octet-stream') {
  const blob = content instanceof Blob ? content : new Blob([content], { type: mimeType })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  setTimeout(() => {
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }, 0)
}

/** RFC 4180-ish CSV serializer; rows = array of arrays. */
export function toCsv(rows) {
  const esc = (v) => {
    if (v == null) return ''
    const s = typeof v === 'string' ? v : String(v)
    return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
  }
  return rows.map((row) => row.map(esc).join(',')).join('\r\n') + '\r\n'
}

export function fuzzyScore(text, pattern) {
  if (!pattern) return 1
  text = text.toLowerCase()
  pattern = pattern.toLowerCase()
  if (text.includes(pattern)) return 100 + (text === pattern ? 100 : 0)
  let score = 0, pi = 0, lastMatch = -1
  for (let ti = 0; ti < text.length && pi < pattern.length; ti++) {
    if (text[ti] === pattern[pi]) {
      score += (ti === lastMatch + 1) ? 2 : 1
      lastMatch = ti
      pi++
    }
  }
  return pi === pattern.length ? score : 0
}
