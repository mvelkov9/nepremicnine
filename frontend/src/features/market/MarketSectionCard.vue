<script setup lang="ts">
  defineProps<{
    eyebrow?: string
    title: string
    description?: string
    featured?: boolean
    compact?: boolean
    tag?: 'section' | 'article' | 'div'
  }>()
</script>

<template>
  <component
    :is="tag || 'section'"
    class="market-section-card"
    :class="{ 'market-section-card--featured': featured, 'market-section-card--compact': compact }"
  >
    <div class="market-section-card__head" :class="{ 'market-section-card__head--compact': compact }">
      <div class="market-section-card__heading">
        <p v-if="eyebrow" class="eyebrow subtle">{{ eyebrow }}</p>
        <h2 class="market-section-card__title">{{ title }}</h2>
        <p v-if="description" class="market-section-card__description">
          {{ description }}
        </p>
      </div>

      <div v-if="$slots.actions" class="market-section-card__actions">
        <slot name="actions" />
      </div>
    </div>

    <slot />
  </component>
</template>

<style scoped>
  .market-section-card {
    position: relative;
    display: grid;
    gap: 1rem;
    padding: 1.15rem;
    border-radius: calc(var(--radius-md) + 0.25rem);
    border: 1px solid color-mix(in srgb, var(--border) 72%, var(--primary) 18%);
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface-strong) 96%, var(--primary-overlay) 4%),
        var(--surface-strong)
      );
    box-shadow: 0 14px 32px color-mix(in srgb, var(--shadow-color) 8%, transparent);
    overflow: hidden;
  }

  .market-section-card::before {
    content: '';
    position: absolute;
    inset: 0 auto auto 0;
    width: 100%;
    height: 0.22rem;
    background: linear-gradient(
      90deg,
      color-mix(in srgb, var(--primary) 84%, white 16%),
      color-mix(in srgb, var(--primary) 26%, transparent)
    );
    opacity: 0.7;
  }

  .market-section-card--featured {
    border-color: color-mix(in srgb, var(--border) 58%, var(--primary) 42%);
    background:
      radial-gradient(circle at top right, color-mix(in srgb, var(--primary) 12%, transparent), transparent 30%),
      linear-gradient(180deg, color-mix(in srgb, var(--surface-panel) 88%, var(--primary) 12%), var(--surface-panel));
  }

  .market-section-card--compact {
    padding: 1rem;
  }

  .market-section-card__head {
    position: relative;
    z-index: 1;
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 0.9rem;
  }

  .market-section-card__head--compact {
    align-items: center;
  }

  .market-section-card__heading {
    display: grid;
    gap: 0.35rem;
    min-width: 0;
  }

  .market-section-card__title {
    margin: 0;
    font-family: var(--font-display);
    font-size: clamp(1.08rem, 1.7vw, 1.45rem);
    line-height: 1.06;
    letter-spacing: -0.03em;
  }

  .market-section-card__description {
    margin: 0;
    max-width: 70ch;
    color: var(--text-muted);
    font-size: 0.95rem;
    line-height: 1.58;
  }

  .market-section-card__actions {
    display: flex;
    flex-wrap: wrap;
    justify-content: flex-end;
    gap: 0.55rem;
  }

  .eyebrow.subtle {
    color: var(--text-soft);
  }

  @media (max-width: 720px) {
    .market-section-card {
      padding: 0.95rem;
    }

    .market-section-card__head {
      flex-direction: column;
    }

    .market-section-card__actions {
      width: 100%;
      justify-content: flex-start;
    }
  }
</style>
