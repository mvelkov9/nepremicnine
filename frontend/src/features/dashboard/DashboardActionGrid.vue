<script setup lang="ts">
  import { RouterLink, type RouteLocationRaw } from 'vue-router'

  defineProps<{
    items: Array<{
      id: string
      label: string
      description: string
      to: RouteLocationRaw
      icon: string
      tone?: 'primary' | 'secondary' | 'success'
    }>
  }>()
</script>

<template>
  <div class="dashboard-action-grid">
    <RouterLink
      v-for="item in items"
      :key="item.id"
      :to="item.to"
      class="dashboard-action-card"
      :class="`tone-${item.tone || 'primary'}`"
    >
      <span class="dashboard-action-icon" aria-hidden="true">
        <i :class="item.icon" />
      </span>
      <strong>{{ item.label }}</strong>
      <small>{{ item.description }}</small>
      <span class="dashboard-action-arrow pi pi-arrow-right" aria-hidden="true" />
    </RouterLink>
  </div>
</template>

<style scoped>
  .dashboard-action-grid {
    display: grid;
    gap: 0.9rem;
    grid-template-columns: repeat(auto-fit, minmax(15rem, 1fr));
  }

  .dashboard-action-card {
    position: relative;
    display: grid;
    gap: 0.45rem;
    min-height: 8rem;
    padding: 1rem 1rem 1rem 1.05rem;
    border-radius: var(--radius-md);
    border: 1px solid color-mix(in srgb, var(--border) 70%, var(--primary) 30%);
    background:
      radial-gradient(circle at top right, color-mix(in srgb, var(--primary) 12%, transparent), transparent 40%),
      linear-gradient(180deg, color-mix(in srgb, var(--surface-card-strong) 96%, transparent), var(--surface-panel));
    color: inherit;
    text-decoration: none;
    box-shadow:
      inset 0 1px 0 var(--glass-highlight),
      var(--shadow-sm);
    transition:
      transform 160ms ease,
      border-color 160ms ease,
      box-shadow 160ms ease;
    overflow: hidden;
  }

  .dashboard-action-card::before {
    content: '';
    position: absolute;
    inset: 0 auto 0 0;
    width: 0.28rem;
    background: linear-gradient(180deg, var(--primary), var(--secondary));
  }

  .dashboard-action-card:hover,
  .dashboard-action-card:focus-visible {
    transform: translateY(-2px);
    border-color: color-mix(in srgb, var(--primary) 34%, var(--border) 66%);
    box-shadow: var(--accent-shadow);
  }

  .dashboard-action-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 2.2rem;
    height: 2.2rem;
    border-radius: 0.85rem;
    background: color-mix(in srgb, var(--primary) 14%, transparent);
    color: var(--primary);
    font-size: 1rem;
  }

  .dashboard-action-card strong {
    font-size: 0.98rem;
    letter-spacing: -0.01em;
  }

  .dashboard-action-card small {
    color: var(--text-muted);
    line-height: 1.5;
  }

  .dashboard-action-arrow {
    align-self: end;
    justify-self: end;
    color: var(--primary);
    opacity: 0.8;
    font-size: 0.95rem;
  }

  .dashboard-action-card.tone-secondary {
    border-color: color-mix(in srgb, var(--border) 76%, var(--secondary) 24%);
  }

  .dashboard-action-card.tone-success {
    border-color: color-mix(in srgb, var(--border) 76%, var(--success) 24%);
  }

  .dashboard-action-card.tone-secondary .dashboard-action-icon {
    background: color-mix(in srgb, var(--secondary) 14%, transparent);
    color: var(--secondary);
  }

  .dashboard-action-card.tone-success .dashboard-action-icon {
    background: color-mix(in srgb, var(--success) 14%, transparent);
    color: var(--success);
  }

  @media (max-width: 680px) {
    .dashboard-action-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
