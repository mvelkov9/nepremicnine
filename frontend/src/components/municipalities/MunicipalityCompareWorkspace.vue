<script setup lang="ts">
  import { computed } from 'vue'
  import { RouterLink } from 'vue-router'
  import Button from 'primevue/button'
  import Select from 'primevue/select'
  import Tag from 'primevue/tag'
  import { useI18n } from 'vue-i18n'
  import EmptyState from '../EmptyState.vue'
  import SectionPanel from '../SectionPanel.vue'
  import type { MunicipalityExplorerItem } from '../../types/api'
  import { formatCurrency, formatNumber } from '../../utils/format'

  type CompareField = 'compareA' | 'compareB' | 'compareC'

  const props = defineProps<{
    options: Array<{ label: string; value: string }>
    compareA: string
    compareB: string
    compareC: string
    rows: MunicipalityExplorerItem[]
    loading?: boolean
    error?: string
  }>()

  const emit = defineEmits<{
    (event: 'update:compare-a', value: string): void
    (event: 'update:compare-b', value: string): void
    (event: 'update:compare-c', value: string): void
    (event: 'retry'): void
  }>()

  const { t } = useI18n()

  const compareSlots = computed(() => [
    {
      key: 'compareA' as const,
      label: t('municipalities.compareFirst'),
      value: props.compareA,
    },
    {
      key: 'compareB' as const,
      label: t('municipalities.compareSecond'),
      value: props.compareB,
    },
    {
      key: 'compareC' as const,
      label: t('municipalities.compareThird'),
      value: props.compareC,
    },
  ])

  const hasSelection = computed(() => Boolean(props.compareA || props.compareB || props.compareC))

  function updateCompareField(field: CompareField, value: string) {
    if (field === 'compareA') emit('update:compare-a', value)
    if (field === 'compareB') emit('update:compare-b', value)
    if (field === 'compareC') emit('update:compare-c', value)
  }
</script>

<template>
  <SectionPanel
    class="municipality-compare-workspace"
    :eyebrow="t('common.compare')"
    :title="t('common.compare')"
  >
    <template #actions>
      <Button
        size="small"
        severity="secondary"
        outlined
        icon="pi pi-refresh"
        :label="t('common.retry')"
        @click="emit('retry')"
      />
    </template>

    <p class="municipality-compare-description">
      {{ t('municipalities.comparePrompt') }}
    </p>

    <div class="compare-grid">
      <label v-for="slot in compareSlots" :key="slot.key" class="compare-field">
        <span>{{ slot.label }}</span>
        <Select
          :model-value="slot.value"
          :options="options"
          option-label="label"
          option-value="value"
          show-clear
          @update:model-value="updateCompareField(slot.key as CompareField, $event)"
        />
      </label>
    </div>

    <div v-if="error && !rows.length" class="state-card state-card-stack" role="alert">
      <EmptyState icon="pi pi-exclamation-triangle" :message="error" />
    </div>

    <p v-else-if="loading && !rows.length" class="compare-status" role="status">
      {{ t('common.loading') }}
    </p>

    <div v-else-if="rows.length" class="compare-cards" :aria-busy="loading">
      <div v-if="error" class="compare-note" role="status">
        <strong>{{ t('common.warning') }}</strong>
        <span>{{ error }}</span>
      </div>
      <article v-for="item in rows" :key="item.slug" class="compare-card">
        <div class="compare-head">
          <div class="compare-heading">
            <span class="compare-kicker">{{ t('dashboard.municipality') }}</span>
            <strong class="compare-name">{{ item.municipality }}</strong>
            <p class="compare-region">{{ item.region || '-' }}</p>
          </div>

          <Tag v-if="item.region" severity="secondary" :value="item.region" />
        </div>

        <dl class="compare-metrics">
          <div>
            <dt>{{ t('dashboard.transactions') }}</dt>
            <dd>{{ formatNumber(item.count) }}</dd>
          </div>
          <div>
            <dt>{{ t('dashboard.medianPrice') }}</dt>
            <dd>{{ formatCurrency(item.median_price) }}</dd>
          </div>
          <div>
            <dt>{{ t('dashboard.pricePerM2') }}</dt>
            <dd>{{ formatCurrency(item.median_price_per_m2) }}/m²</dd>
          </div>
        </dl>

        <RouterLink :to="`/obcine/${item.slug}`" class="compare-link">
          {{ t('municipalities.viewDetail') }}
        </RouterLink>
      </article>
    </div>

    <EmptyState
      v-else
      :message="hasSelection ? t('common.noData') : t('municipalities.comparePrompt')"
    />
  </SectionPanel>
</template>

<style scoped>
  .municipality-compare-workspace {
    gap: 1rem;
  }

  .municipality-compare-description {
    margin: -0.15rem 0 0;
    max-width: 68ch;
    color: var(--text-muted);
    line-height: 1.65;
  }

  .compare-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0.9rem;
  }

  .compare-field {
    display: grid;
    gap: 0.35rem;
    min-width: 0;
  }

  .compare-field span {
    font-size: var(--text-xs);
    font-weight: 800;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--text-soft);
  }

  .compare-field :deep(.p-select) {
    width: 100%;
  }

  .compare-status {
    margin: 0;
    color: var(--text-soft);
    font-size: 0.95rem;
  }

  .compare-cards {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(18rem, 1fr));
    gap: 1rem;
  }

  .compare-note {
    grid-column: 1 / -1;
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.8rem 0.95rem;
    border-radius: calc(var(--radius-sm) + 0.1rem);
    border: 1px solid color-mix(in srgb, var(--warning) 38%, var(--border) 62%);
    background: color-mix(in srgb, var(--surface-card-strong) 92%, var(--warning) 8%);
    color: var(--text-muted);
  }

  .compare-note strong {
    color: var(--text);
    font-size: var(--text-sm);
    letter-spacing: -0.01em;
  }

  .compare-card {
    display: grid;
    gap: 0.95rem;
    min-height: 100%;
  }

  .compare-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 0.9rem;
  }

  .compare-heading {
    display: grid;
    gap: 0.22rem;
    min-width: 0;
  }

  .compare-kicker {
    font-size: 0.68rem;
    font-weight: 800;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: var(--text-soft);
  }

  .compare-name {
    font-size: 1.02rem;
    line-height: 1.14;
    letter-spacing: -0.02em;
    text-wrap: balance;
  }

  .compare-region {
    margin: 0;
    color: var(--text-muted);
    font-size: 0.9rem;
  }

  .compare-metrics {
    display: grid;
    gap: 0.7rem;
    margin: 0;
  }

  .compare-metrics div {
    display: grid;
    gap: 0.24rem;
    padding: 0.86rem 0.95rem;
    border-radius: calc(var(--radius-sm) + 0.15rem);
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface-card-strong) 92%, transparent),
        transparent 120%
      ),
      var(--surface-subtle);
    border: 1px solid color-mix(in srgb, var(--border) 72%, var(--content-border-strong) 28%);
    box-shadow: inset 0 1px 0 var(--content-glow);
  }

  .compare-metrics dt {
    margin: 0;
    font-size: var(--text-xs);
    color: var(--text-soft);
    font-weight: 800;
    letter-spacing: 0.09em;
    text-transform: uppercase;
  }

  .compare-metrics dd {
    margin: 0;
    font-size: 1rem;
    font-weight: 700;
    letter-spacing: -0.02em;
  }

  .compare-link {
    width: fit-content;
    font-weight: 700;
    color: var(--link);
    text-underline-offset: 0.16em;
    text-decoration-thickness: 0.09em;
  }

  @media (max-width: 1100px) {
    .compare-grid {
      grid-template-columns: 1fr;
    }
  }

  @media (max-width: 720px) {
    .compare-note {
      flex-direction: column;
      align-items: flex-start;
    }

    .compare-head {
      flex-direction: column;
    }

    .compare-cards {
      grid-template-columns: 1fr;
    }
  }
</style>
