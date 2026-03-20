<template>
  <Teleport to="body">
    <Transition name="page-loader">
      <div v-if="show" class="page-loader-overlay" role="status" aria-label="Loading">
        <div class="page-loader-bar" />
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
    pointer-events: none;
    background: linear-gradient(
      180deg,
      color-mix(in srgb, var(--backdrop-scrim) 18%, transparent),
      transparent 16%
    );
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
