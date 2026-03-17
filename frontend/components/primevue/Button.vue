<script setup>
  const props = defineProps({
    label: { type: String, default: '' },
    icon: { type: String, default: '' },
    severity: { type: String, default: 'primary' },
    outlined: { type: Boolean, default: false },
    text: { type: Boolean, default: false },
    rounded: { type: Boolean, default: false },
    loading: { type: Boolean, default: false },
    disabled: { type: Boolean, default: false },
    type: { type: String, default: 'button' },
  })

  defineEmits(['click'])

  const iconMap = {
    'pi pi-arrow-left': '←',
    'pi pi-arrow-right': '→',
    'pi pi-bars': '☰',
    'pi pi-bolt': '⚡',
    'pi pi-cog': '⋯',
    'pi pi-database': '◫',
    'pi pi-download': '↓',
    'pi pi-external-link': '↗',
    'pi pi-map': '⌖',
    'pi pi-map-marker': '⌖',
    'pi pi-times': '×',
    'pi pi-trash': '⌫',
    'pi pi-upload': '↑',
    'pi pi-users': '◌',
  }

  const iconGlyph = computed(() => {
    if (!props.icon) return ''
    return iconMap[props.icon] || '•'
  })

  const semanticClass = computed(() => {
    if (props.severity === 'success') return 'border-[var(--ui-success)] text-[var(--ui-success)]'
    if (props.severity === 'warn') return 'border-[var(--ui-warning)] text-[var(--ui-warning)]'
    if (props.severity === 'danger') return 'border-[var(--ui-error)] text-[var(--ui-error)]'
    if (props.severity === 'contrast')
      return 'border-[var(--ui-secondary)] text-[var(--ui-secondary)]'
    if (props.severity === 'secondary') return 'border-[var(--ui-border)] text-[var(--ui-text)]'
    return 'border-[var(--ui-primary)] text-[var(--ui-primary)]'
  })

  const toneClass = computed(() => {
    if (props.text) return [semanticClass.value, 'p-button--text bg-transparent shadow-none']
    if (props.outlined) {
      return [semanticClass.value, 'p-button--outlined bg-transparent']
    }
    if (props.severity === 'success') {
      return 'p-button--success border-[var(--ui-success)] text-[var(--ui-bg-inverted)]'
    }
    if (props.severity === 'warn') {
      return 'p-button--warn border-[var(--ui-warning)] text-[var(--ui-bg-inverted)]'
    }
    if (props.severity === 'danger') {
      return 'p-button--danger border-[var(--ui-error)] text-[var(--ui-bg-inverted)]'
    }
    if (props.severity === 'secondary' || props.severity === 'contrast') {
      return 'p-button--secondary border-[var(--ui-border)] text-[var(--ui-text)]'
    }
    return 'p-button--primary border-[var(--ui-primary)] text-white'
  })
</script>

<template>
  <button
    :type="type"
    class="p-button inline-flex min-h-11 items-center justify-center gap-2 border px-4 py-2 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-60"
    :class="[rounded ? 'rounded-full' : 'rounded-2xl', toneClass]"
    :disabled="disabled || loading"
    :aria-busy="loading ? 'true' : 'false'"
    @click="$emit('click', $event)"
  >
    <span
      v-if="loading"
      class="p-button-icon h-4 w-4 animate-spin rounded-full border-2 border-current border-r-transparent"
    ></span>
    <span v-else-if="icon" class="p-button-icon text-sm">{{ iconGlyph }}</span>
    <slot>
      <span v-if="label" class="p-button-label">{{ label }}</span>
    </slot>
  </button>
</template>

<style scoped>
  .p-button {
    position: relative;
    overflow: hidden;
    box-shadow: 0 14px 30px rgb(15 23 42 / 10%);
    transition:
      transform 160ms ease,
      box-shadow 160ms ease,
      border-color 160ms ease,
      background 160ms ease,
      color 160ms ease,
      filter 160ms ease;
  }

  .p-button:hover:not(:disabled) {
    transform: translateY(-2px);
    filter: saturate(1.05);
    box-shadow: 0 18px 36px rgb(15 23 42 / 16%);
  }

  .p-button:active:not(:disabled) {
    transform: translateY(0) scale(0.98);
    filter: saturate(0.96);
  }

  .p-button:focus-visible {
    outline: none;
    box-shadow:
      0 0 0 4px color-mix(in srgb, var(--ui-primary) 18%, transparent),
      0 18px 36px rgb(15 23 42 / 16%);
  }

  .p-button--primary {
    background: linear-gradient(
      135deg,
      color-mix(in srgb, var(--ui-primary) 86%, white 6%),
      color-mix(in srgb, var(--ui-secondary) 18%, var(--ui-primary) 82%)
    );
  }

  .p-button--secondary {
    background: var(--surface-strong);
  }

  .p-button--success {
    background: linear-gradient(
      135deg,
      color-mix(in srgb, var(--ui-success) 88%, white 6%),
      color-mix(in srgb, var(--ui-success) 76%, var(--ui-secondary) 12%)
    );
  }

  .p-button--warn {
    background: linear-gradient(
      135deg,
      color-mix(in srgb, var(--ui-warning) 88%, white 8%),
      color-mix(in srgb, var(--ui-warning) 76%, var(--ui-secondary) 18%)
    );
  }

  .p-button--danger {
    background: linear-gradient(
      135deg,
      color-mix(in srgb, var(--ui-error) 88%, white 8%),
      color-mix(in srgb, var(--ui-error) 78%, var(--ui-warning) 12%)
    );
  }

  .p-button--outlined,
  .p-button--text {
    box-shadow: 0 10px 22px rgb(15 23 42 / 6%);
  }

  .p-button--outlined {
    background: var(--surface-strong);
  }

  .p-button--text {
    color: var(--ui-primary);
    background: color-mix(in srgb, var(--ui-primary) 6%, transparent);
  }

  .p-button--outlined:hover:not(:disabled),
  .p-button--text:hover:not(:disabled) {
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--ui-primary) 12%, transparent),
      color-mix(in srgb, var(--ui-secondary) 8%, transparent)
    );
  }
</style>
