<template>
  <Teleport to="body">
    <Transition name="page-loader">
      <div v-if="show" class="page-loader-overlay" role="status" aria-label="Loading">
        <div class="page-loader-glow"></div>
        <div class="page-loader-shell">
          <div class="page-loader-bar"></div>
          <span class="page-loader-label">Loading</span>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
  defineProps<{ show: boolean }>()
</script>

<style scoped>
  .page-loader-overlay {
    position: fixed;
    inset: 0;
    z-index: 9998;
    display: grid;
    place-items: start center;
    padding-top: 0;
    pointer-events: none;
    background:
      radial-gradient(
        circle at 50% 0%,
        color-mix(in srgb, var(--primary) 14%, transparent),
        transparent 36%
      ),
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--backdrop-scrim) 20%, transparent),
        transparent 20%
      );
  }

  .page-loader-glow {
    position: absolute;
    inset: 0;
    background:
      radial-gradient(
        circle at 50% 0%,
        color-mix(in srgb, var(--primary) 12%, transparent),
        transparent 24%
      ),
      radial-gradient(
        circle at 50% 12%,
        color-mix(in srgb, var(--secondary) 8%, transparent),
        transparent 20%
      );
    opacity: 0.7;
  }

  .page-loader-shell {
    position: relative;
    width: min(100%, 96rem);
    padding-inline: 0;
  }

  .page-loader-bar {
    position: absolute;
    top: 0;
    left: 0;
    height: 3px;
    background: linear-gradient(90deg, var(--primary), var(--secondary));
    border-radius: 0 999px 999px 0;
    box-shadow: 0 0 18px color-mix(in srgb, var(--primary) 26%, transparent);
    animation: loader-bar 1.4s cubic-bezier(0.4, 0, 0.2, 1) infinite;
  }

  .page-loader-label {
    position: absolute;
    top: 0.8rem;
    left: 50%;
    transform: translateX(-50%);
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    padding: 0.45rem 0.8rem;
    border-radius: 999px;
    border: 1px solid color-mix(in srgb, var(--border) 68%, var(--content-border-strong) 32%);
    background: color-mix(in srgb, var(--surface-card-strong) 90%, transparent);
    color: var(--text-muted);
    font-size: 0.72rem;
    font-weight: 800;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    box-shadow: var(--shadow-sm);
  }

  @keyframes loader-bar {
    0% {
      width: 0%;
      opacity: 1;
    }
    65% {
      width: 88%;
      opacity: 1;
    }
    95% {
      width: 100%;
      opacity: 0.5;
    }
    100% {
      width: 100%;
      opacity: 0;
    }
  }

  .page-loader-enter-active,
  .page-loader-leave-active {
    transition: opacity 200ms ease;
  }

  .page-loader-enter-from,
  .page-loader-leave-to {
    opacity: 0;
  }
</style>
