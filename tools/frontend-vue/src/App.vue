<template>
  <div class="page">
    <nav class="nav">
      <router-link to="/clips">Clips</router-link>
      <router-link to="/results">Results</router-link>
      <router-link to="/ai-optimization">AI 优化</router-link>
    </nav>
    <router-view />
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'

const THEME_KEY = 'centerpoint-theme'
const theme = ref('dark')
const themeReady = ref(false)

const themeLabel = computed(() =>
  theme.value === 'dark' ? 'Switch to day mode' : 'Switch to night mode'
)

function applyTheme(nextTheme) {
  document.documentElement.setAttribute('data-theme', nextTheme)
}

function toggleTheme() {
  theme.value = theme.value === 'dark' ? 'light' : 'dark'
}

onMounted(() => {
  const savedTheme = window.localStorage.getItem(THEME_KEY)
  if (savedTheme === 'light' || savedTheme === 'dark') {
    theme.value = savedTheme
  }
  applyTheme(theme.value)
  themeReady.value = true
})

watch(theme, (nextTheme) => {
  if (!themeReady.value) return
  applyTheme(nextTheme)
  window.localStorage.setItem(THEME_KEY, nextTheme)
})
</script>

<style scoped>
.page-shell {
  min-height: 100vh;
}

.topbar {
  width: min(1500px, calc(100vw - 32px));
  margin: 0 auto;
  padding-top: 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.theme-toggle {
  position: relative;
  width: 56px;
  height: 56px;
  border: 0;
  border-radius: 999px;
  background: transparent;
  box-shadow: none;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  transition:
    transform .22s var(--ease-out),
    border-color .22s var(--ease-out),
    box-shadow .22s var(--ease-out),
    background .28s var(--ease-out);
}

.theme-toggle:hover {
  transform: translateY(-2px) scale(1.04);
}

.theme-toggle:active {
  transform: scale(.96);
}

.theme-toggle:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 4px;
}

.theme-toggle__halo {
  position: absolute;
  inset: 6px;
  border-radius: 999px;
  background: linear-gradient(180deg, var(--toggle-bg-top), var(--toggle-bg-bottom));
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.12),
    var(--toggle-shadow);
  opacity: 1;
  transition:
    opacity .28s var(--ease-out),
    transform .28s var(--ease-out),
    background .28s var(--ease-out),
    box-shadow .28s var(--ease-out);
}

.theme-toggle__halo::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  background: var(--toggle-halo);
  opacity: .95;
}

.theme-toggle:hover .theme-toggle__halo {
  transform: scale(1.06);
}

.theme-toggle__icon {
  position: relative;
  z-index: 1;
  width: 32px;
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.theme-icon {
  width: 28px;
  height: 28px;
  color: var(--toggle-icon);
  filter: drop-shadow(0 2px 10px var(--toggle-icon-soft));
  transition:
    color .28s var(--ease-out),
    transform .22s var(--ease-out),
    filter .28s var(--ease-out);
}

.theme-toggle:hover .theme-icon {
  transform: rotate(10deg) scale(1.04);
}

@media (max-width: 900px) {
  .topbar {
    align-items: flex-start;
    flex-direction: column;
  }

  .theme-toggle {
    width: 52px;
    height: 52px;
  }
}
</style>
