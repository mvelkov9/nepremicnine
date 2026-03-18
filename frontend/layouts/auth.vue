<script setup lang="ts">
  // Auth layout — full-screen atmospheric login stage
</script>

<template>
  <div class="shell-surface auth-stage">
    <div class="auth-atmosphere" aria-hidden="true">
      <span class="auth-orb auth-orb-primary" />
      <span class="auth-orb auth-orb-secondary" />
      <span class="auth-grid" />
    </div>

    <main class="auth-main">
      <slot />
    </main>
  </div>
</template>
