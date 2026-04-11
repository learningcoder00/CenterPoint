<template>
  <div class="page-shell">
    <header class="topbar">
      <nav class="nav" aria-label="Primary">
        <router-link to="/clips">Clips</router-link>
        <router-link to="/results">Results</router-link>
      </nav>

      <button
        type="button"
        class="theme-toggle"
        :aria-label="themeLabel"
        :title="themeLabel"
        @click="toggleTheme"
      >
        <span class="theme-toggle__halo"></span>
        <span class="theme-toggle__icon" aria-hidden="true">
          <svg
            v-if="theme === 'dark'"
            class="theme-icon"
            viewBox="0 0 24 24"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              d="M18 14.5A6.5 6.5 0 0 1 9.5 6a7.5 7.5 0 1 0 8.5 8.5Z"
              stroke="currentColor"
              stroke-width="1.8"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
            <path
              d="M17.7 5.2v2.6M16.4 6.5H19M6 3.6v1.8M5.1 4.5h1.8"
              stroke="currentColor"
              stroke-width="1.8"
              stroke-linecap="round"
            />
          </svg>
          <svg
            v-else
            class="theme-icon"
            viewBox="0 0 24 24"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <circle cx="12" cy="12" r="4.2" stroke="currentColor" stroke-width="1.8" />
            <path
              d="M12 2.8v2.4M12 18.8v2.4M21.2 12h-2.4M5.2 12H2.8M18.5 5.5l-1.7 1.7M7.2 16.8l-1.7 1.7M18.5 18.5l-1.7-1.7M7.2 7.2 5.5 5.5"
              stroke="currentColor"
              stroke-width="1.8"
              stroke-linecap="round"
            />
          </svg>
        </span>
      </button>
    </header>

    <div class="page">
      <router-view />
    </div>
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
