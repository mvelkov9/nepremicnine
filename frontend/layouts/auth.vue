<script setup>
  import ToastStack from '~/components/shell/ToastStack.vue'
</script>

<template>
  <div class="shell-surface auth-stage">
    <ToastStack />
    <div class="auth-atmosphere" aria-hidden="true">
      <span class="auth-orb auth-orb-primary"></span>
      <span class="auth-orb auth-orb-secondary"></span>
      <span class="auth-grid"></span>
    </div>
    <main class="auth-main">
      <slot />
    </main>
  </div>
</template>
