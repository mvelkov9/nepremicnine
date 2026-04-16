<script setup lang="ts">
  import InputText from 'primevue/inputtext'
  import ToggleSwitch from 'primevue/toggleswitch'
  import { useI18n } from 'vue-i18n'
  import type { PrepareEnrichmentOptionDefinition, PrepareEnrichmentState } from './types'

  const props = defineProps<{
    title: string
    description: string
    modelValue: PrepareEnrichmentState
    options: PrepareEnrichmentOptionDefinition[]
    variantPlaceholder: string
  }>()

  const emit = defineEmits<{
    'update:modelValue': [value: PrepareEnrichmentState]
  }>()

  const { t } = useI18n()

  function updateField<K extends keyof PrepareEnrichmentState>(
    key: K,
    value: PrepareEnrichmentState[K],
  ) {
    emit('update:modelValue', {
      ...props.modelValue,
      [key]: value,
    })
  }
</script>

<template>
  <section class="prepare-enrichment-panel">
    <div class="prepare-enrichment-head">
      <h3>{{ title }}</h3>
      <p class="muted">{{ description }}</p>
    </div>

    <div class="prepare-enrichment-cards">
      <label
        v-for="opt in options"
        :key="opt.key"
        class="prepare-enrichment-card"
        :class="{ 'prepare-enrichment-card--active': modelValue[opt.key] }"
      >
        <div class="prepare-enrichment-card-head">
          <div class="prepare-enrichment-card-title">
            <i :class="`pi ${opt.icon}`" />
            <span>{{ t(opt.titleKey) }}</span>
          </div>
          <ToggleSwitch
            :model-value="modelValue[opt.key]"
            @update:model-value="updateField(opt.key, Boolean($event))"
          />
        </div>
        <p class="prepare-enrichment-card-copy">{{ t(opt.descKey) }}</p>
        <div class="prepare-enrichment-card-files">
          <span class="files-label">{{ t('prepare.enrichmentFilesLabel') }}:</span>
          <code>{{ t(opt.filesKey) }}</code>
        </div>
      </label>
    </div>

    <div class="prepare-enrichment-variant">
      <label class="form-label">{{ t('prepare.variantLabel') }}</label>
      <InputText
        :model-value="modelValue.variant_label"
        :placeholder="variantPlaceholder"
        @update:model-value="updateField('variant_label', String($event ?? ''))"
      />
    </div>
  </section>
</template>

<style scoped>
  .prepare-enrichment-panel {
    display: grid;
    gap: 0.9rem;
    padding: 1rem;
    border-radius: var(--radius-md);
    border: 1px solid color-mix(in srgb, var(--border) 80%, var(--content-border-strong) 20%);
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface-card-strong) 96%, transparent),
        transparent 120%
      ),
      var(--surface-panel);
    box-shadow:
      inset 0 1px 0 var(--content-glow),
      var(--shadow-sm);
  }

  .prepare-enrichment-head {
    display: grid;
    gap: 0.35rem;
  }

  .prepare-enrichment-head h3 {
    margin: 0;
    font-size: 1rem;
    font-family: var(--font-display);
  }

  .prepare-enrichment-cards {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
    gap: 0.75rem;
  }

  .prepare-enrichment-card {
    display: grid;
    gap: 0.5rem;
    padding: 0.9rem 1rem;
    border: 1px solid color-mix(in srgb, var(--border) 80%, var(--content-border-strong) 20%);
    border-radius: var(--radius-sm);
    background: var(--surface);
    cursor: pointer;
    transition:
      transform 0.15s ease,
      border-color 0.15s ease,
      background 0.15s ease;
  }

  .prepare-enrichment-card:hover {
    transform: translateY(-1px);
  }

  .prepare-enrichment-card--active {
    border-color: color-mix(in srgb, var(--primary) 42%, var(--border));
    background: color-mix(in srgb, var(--primary) 5%, var(--surface));
  }

  .prepare-enrichment-card-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 0.5rem;
  }

  .prepare-enrichment-card-title {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-weight: 700;
    font-size: 0.9rem;
  }

  .prepare-enrichment-card-title .pi {
    color: var(--primary);
  }

  .prepare-enrichment-card-copy {
    margin: 0;
    color: var(--text-muted);
    font-size: var(--text-sm);
    line-height: 1.5;
  }

  .prepare-enrichment-card-files {
    display: flex;
    align-items: baseline;
    gap: 0.35rem;
    font-size: var(--text-xs);
    flex-wrap: wrap;
  }

  .files-label {
    color: var(--text-muted);
    white-space: nowrap;
  }

  .prepare-enrichment-card-files code {
    font-size: var(--text-xs);
    color: var(--text-muted);
    background: var(--surface-muted);
    padding: 0.12rem 0.4rem;
    border-radius: 999px;
    word-break: break-all;
  }

  .prepare-enrichment-variant {
    max-width: 24rem;
    display: grid;
    gap: 0.35rem;
  }
</style>
