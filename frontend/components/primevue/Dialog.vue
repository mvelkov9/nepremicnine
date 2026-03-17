<script setup>
  defineOptions({ inheritAttrs: false })

  const attrs = useAttrs()
  const props = defineProps({
    visible: { type: Boolean, default: false },
    header: { type: String, default: '' },
    modal: { type: Boolean, default: false },
    dismissableMask: { type: Boolean, default: true },
  })

  const emit = defineEmits(['update:visible'])

  function close() {
    emit('update:visible', false)
  }
</script>

<template>
  <Teleport to="body">
    <div v-if="visible" class="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div
        class="absolute inset-0 bg-black/65 backdrop-blur-[2px]"
        @click="dismissableMask ? close() : null"
      ></div>

      <div
        v-bind="attrs"
        class="p-dialog relative z-10 w-full max-w-5xl rounded-[1.75rem] border border-[var(--ui-border)] shadow-2xl shadow-black/20"
        style="background: var(--surface-strong)"
      >
        <div
          class="p-dialog-header flex items-center justify-between gap-4 border-b border-[var(--ui-border)] px-6 py-4"
          style="
            background: linear-gradient(
              145deg,
              color-mix(in srgb, var(--surface-strong) 94%, transparent),
              color-mix(in srgb, var(--ui-primary) 6%, transparent)
            );
          "
        >
          <h3 class="text-lg font-semibold">{{ header }}</h3>
          <button type="button" class="rounded-full px-3 py-1 text-xl" @click="close">×</button>
        </div>
        <div
          class="p-dialog-content max-h-[75vh] overflow-auto px-6 py-5"
          style="background: var(--surface-strong)"
        >
          <slot />
        </div>
        <div v-if="$slots.footer" class="border-t border-[var(--ui-border)] px-6 py-4">
          <slot name="footer" />
        </div>
      </div>
    </div>
  </Teleport>
</template>
