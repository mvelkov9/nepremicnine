<template>
  <article class="rounded-[1.5rem] border border-[var(--ui-border)] bg-[var(--ui-bg-elevated)] p-5 shadow-sm shadow-black/5">
    <header v-if="$slots.title" class="mb-4">
      <slot name="title" />
    </header>
    <div>
      <slot name="content">
        <slot />
      </slot>
    </div>
    <footer v-if="$slots.footer" class="mt-4">
      <slot name="footer" />
    </footer>
  </article>
</template>
