<script setup>
  import { useToast } from '../composables/useToast'

  const { toasts } = useToast()

  function dismiss(id) {
    toasts.value = toasts.value.filter((t) => t.id !== id)
  }
</script>

<template>
  <Teleport to="body">
    <div class="toast-container">
      <TransitionGroup name="toast">
        <div
          v-for="toast in toasts"
          :key="toast.id"
          class="toast-item"
          :class="'toast-' + toast.type"
          @click="dismiss(toast.id)"
        >
          {{ toast.message }}
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<style scoped>
  .toast-container {
    position: fixed;
    bottom: 1rem;
    right: 1rem;
    z-index: 9999;
    display: flex;
    flex-direction: column-reverse;
    gap: 0.5rem;
    max-width: 24rem;
  }

  .toast-item {
    padding: 0.75rem 1rem;
    border-radius: 0.375rem;
    color: #fff;
    font-size: 0.875rem;
    cursor: pointer;
    box-shadow: 0 4px 12px rgb(0 0 0 / 15%);
  }

  .toast-info {
    background: #3b82f6;
  }
  .toast-success {
    background: #22c55e;
  }
  .toast-warning {
    background: #f59e0b;
  }
  .toast-error {
    background: #ef4444;
  }

  .toast-enter-active,
  .toast-leave-active {
    transition: all 0.3s ease;
  }
  .toast-enter-from {
    opacity: 0;
    transform: translateX(2rem);
  }
  .toast-leave-to {
    opacity: 0;
    transform: translateX(2rem);
  }
</style>
