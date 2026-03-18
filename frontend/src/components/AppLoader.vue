<script setup>
  defineProps({
    visible: { type: Boolean, default: false },
    label: { type: String, default: '' },
    mode: {
      type: String,
      default: 'overlay',
      validator: (value) => ['overlay', 'fullscreen'].includes(value),
    },
  })
</script>

<template>
  <transition name="app-loader-fade">
    <div
      v-if="visible"
      class="app-loader"
      :class="mode"
      role="status"
      :aria-label="label || 'Loading'"
      aria-live="polite"
    >
      <div class="app-loader-card">
        <span class="app-loader-ring" aria-hidden="true"></span>
        <span class="app-loader-label">{{ label }}</span>
      </div>
    </div>
  </transition>
</template>

<style scoped>
  .app-loader {
    position: fixed;
    inset: 0;
    z-index: 1200;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 1.5rem;
    pointer-events: none;
  }

  .app-loader.fullscreen {
    background:
      linear-gradient(180deg, rgb(255 255 255 / 76%), rgb(238 243 247 / 88%)), var(--bg-accent);
    backdrop-filter: blur(18px);
  }

  [data-theme='dark'] .app-loader.fullscreen {
    background: linear-gradient(180deg, rgb(8 16 29 / 80%), rgb(8 16 29 / 92%)), var(--bg-accent);
  }

  .app-loader.overlay {
    align-items: flex-start;
    justify-content: flex-end;
    padding: 1.25rem;
  }

  .app-loader-card {
    display: inline-flex;
    align-items: center;
    gap: 0.8rem;
    min-width: 12rem;
    padding: 0.95rem 1.15rem;
    border-radius: 999px;
    border: 1px solid var(--border-strong);
    background: color-mix(in srgb, var(--surface-strong) 88%, transparent);
    box-shadow: var(--shadow-lg);
    color: var(--text);
  }

  .app-loader.fullscreen .app-loader-card {
    padding: 1rem 1.3rem;
  }

  .app-loader-ring {
    width: 1rem;
    height: 1rem;
    border-radius: 999px;
    border: 2px solid color-mix(in srgb, var(--primary) 22%, var(--border));
    border-top-color: var(--primary);
    animation: app-loader-spin 0.8s linear infinite;
    flex-shrink: 0;
  }

  .app-loader-label {
    font-size: 0.82rem;
    font-weight: 700;
    letter-spacing: 0.03em;
  }

  .app-loader-fade-enter-active,
  .app-loader-fade-leave-active {
    transition: opacity 180ms ease;
  }

  .app-loader-fade-enter-from,
  .app-loader-fade-leave-to {
    opacity: 0;
  }

  @keyframes app-loader-spin {
    to {
      transform: rotate(360deg);
    }
  }
</style>
