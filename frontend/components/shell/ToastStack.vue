<script setup>
  import { useToast } from '~/legacy/composables/useToast'

  const { toasts } = useToast()

  function dismiss(id) {
    toasts.value = toasts.value.filter((toast) => toast.id !== id)
  }
</script>

<template>
  <Teleport to="body">
    <div class="fixed inset-x-4 top-4 z-[100] flex flex-col gap-3 sm:left-auto sm:right-4 sm:w-96">
      <TransitionGroup name="toast-stack">
        <button
          v-for="toast in toasts"
          :key="toast.id"
          type="button"
          class="rounded-2xl border border-[var(--ui-border)] bg-[var(--ui-bg-elevated)] px-4 py-3 text-left text-sm text-[var(--ui-text)] shadow-lg shadow-black/5 backdrop-blur"
          @click="dismiss(toast.id)"
        >
          <span
            class="mb-1 inline-flex rounded-full px-2 py-0.5 text-[11px] font-semibold uppercase tracking-[0.18em]"
            :class="{
              'bg-[var(--ui-primary)]/10 text-[var(--ui-primary)]': toast.type === 'info',
              'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400': toast.type === 'success',
              'bg-amber-500/10 text-amber-600 dark:text-amber-400': toast.type === 'warning',
              'bg-red-500/10 text-red-600 dark:text-red-400': toast.type === 'error',
            }"
          >
            {{ toast.type }}
          </span>
          <div>{{ toast.message }}</div>
        </button>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<style scoped>
  .toast-stack-enter-active,
  .toast-stack-leave-active {
    transition: all 180ms ease;
  }

  .toast-stack-enter-from,
  .toast-stack-leave-to {
    opacity: 0;
    transform: translateY(-8px);
  }
</style>
