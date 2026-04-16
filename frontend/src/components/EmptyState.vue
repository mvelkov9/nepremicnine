<script setup lang="ts">
  import { computed } from 'vue'

  const props = defineProps<{
    icon?: string
    message: string
  }>()

  const iconClass = computed(() => {
    const value = String(props.icon || 'i').trim()
    if (!value) return 'pi pi-info-circle'
    if (value.startsWith('pi ')) return value
    if (value.startsWith('pi-') || value.startsWith('icon-')) return value

    const iconMap: Record<string, string> = {
      i: 'pi pi-info-circle',
      info: 'pi pi-info-circle',
      '!': 'pi pi-exclamation-triangle',
      warning: 'pi pi-exclamation-triangle',
      folder: 'pi pi-folder-open',
      '\u{1F4C1}': 'pi pi-folder-open',
      compass: 'pi pi-compass',
      '\u{1F9ED}': 'pi pi-compass',
      chart: 'pi pi-chart-bar',
      '\u{1F4CA}': 'pi pi-chart-bar',
      search: 'pi pi-search',
      inbox: 'pi pi-inbox',
      map: 'pi pi-map-marker',
      file: 'pi pi-file',
    }

    const normalized = value.toLowerCase()
    if (iconMap[normalized]) return iconMap[normalized]
    if (iconMap[value]) return iconMap[value]

    return 'pi pi-info-circle'
  })
</script>

<template>
  <div class="empty-state" role="status" :aria-label="message">
    <span class="empty-icon" aria-hidden="true">
      <i :class="iconClass"></i>
    </span>
    <div class="empty-copy">
      <p class="empty-message">{{ message }}</p>
    </div>
  </div>
</template>

<style scoped>
  .empty-state {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    gap: 1rem;
    align-items: center;
    min-height: 11rem;
    padding: 1.35rem;
    border-radius: var(--radius-md);
    border: 1px solid color-mix(in srgb, var(--border) 80%, var(--content-border-strong) 20%);
    background:
      radial-gradient(
        circle at top left,
        color-mix(in srgb, var(--primary) 10%, transparent),
        transparent 28%
      ),
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface-card-strong) 98%, transparent),
        transparent 120%
      ),
      var(--surface-panel);
    box-shadow:
      inset 0 1px 0 var(--content-glow),
      var(--shadow-sm);
  }

  .empty-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 4rem;
    height: 4rem;
    font-size: 1.8rem;
    line-height: 1;
    border-radius: var(--radius-md);
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--surface-card-strong) 92%, var(--primary) 8%),
      var(--surface-subtle)
    );
    border: 1px solid color-mix(in srgb, var(--border) 76%, var(--primary) 24%);
    color: var(--primary);
    box-shadow:
      inset 0 1px 0 var(--content-glow),
      0 12px 24px color-mix(in srgb, var(--primary) 10%, transparent);
  }

  .empty-copy {
    display: grid;
    gap: 0.35rem;
    min-width: 0;
  }

  .empty-message {
    margin: 0;
    color: var(--text-soft);
    font-size: 0.98rem;
    line-height: 1.65;
    max-width: 42ch;
    text-wrap: balance;
    text-align: left;
  }

  @media (max-width: 520px) {
    .empty-state {
      grid-template-columns: 1fr;
      justify-items: center;
      text-align: center;
    }

    .empty-message {
      text-align: center;
    }
  }
</style>
