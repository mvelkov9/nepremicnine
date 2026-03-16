<script setup>
  defineProps({
    name: {
      type: String,
      required: true,
    },
    size: {
      type: [Number, String],
      default: 18,
    },
    stroke: {
      type: Number,
      default: 1.8,
    },
  })
</script>

<template>
  <svg
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    stroke="currentColor"
    stroke-linecap="round"
    stroke-linejoin="round"
    :stroke-width="stroke"
    aria-hidden="true"
  >
    <template v-if="name === 'dashboard'">
      <path d="M4 5.5h7v5H4z" />
      <path d="M13 5.5h7v8h-7z" />
      <path d="M4 12.5h7V20H4z" />
      <path d="M13 15.5h7V20h-7z" />
    </template>

    <template v-else-if="name === 'data'">
      <path d="M4 6.5C4 4.6 7.6 3 12 3s8 1.6 8 3.5S16.4 10 12 10 4 8.4 4 6.5Z" />
      <path d="M4 12c0 1.9 3.6 3.5 8 3.5s8-1.6 8-3.5" />
      <path d="M4 17.5c0 1.9 3.6 3.5 8 3.5s8-1.6 8-3.5" />
      <path d="M4 6.5v11" />
      <path d="M20 6.5v11" />
    </template>

    <template v-else-if="name === 'prepare'">
      <path d="M5 6h14" />
      <path d="M8 12h8" />
      <path d="M10 18h4" />
      <path d="M7 4v4" />
      <path d="M17 10v4" />
      <path d="M12 16v4" />
    </template>

    <template v-else-if="name === 'model'">
      <path d="M4 18.5 9 12l3 3 6-8" />
      <path d="M4 20.5h16" />
      <circle cx="9" cy="12" r="1.25" fill="currentColor" stroke="none" />
      <circle cx="12" cy="15" r="1.25" fill="currentColor" stroke="none" />
      <circle cx="18" cy="7" r="1.25" fill="currentColor" stroke="none" />
    </template>

    <template v-else-if="name === 'prediction'">
      <path d="M5 17.5 10 12l3.2 2.8L19 7.5" />
      <path d="M17 7.5h2v2" />
      <path d="M4 20.5h16" />
    </template>

    <template v-else-if="name === 'map'">
      <path d="M8 4.5 16 7.5 21 5.5v14l-5 2-8-3-5 2v-14z" />
      <path d="M8 4.5v14" />
      <path d="M16 7.5v14" />
    </template>

    <template v-else-if="name === 'diagnostics'">
      <path d="M4 18.5h4v-6H4z" />
      <path d="M10 18.5h4v-10h-4z" />
      <path d="M16 18.5h4v-3h-4z" />
      <path d="M3 20.5h18" />
    </template>

    <template v-else-if="name === 'analysis'">
      <circle cx="11" cy="11" r="5.5" />
      <path d="m19 19-3.5-3.5" />
      <path d="M11 8.5v5" />
      <path d="M8.5 11H13" />
    </template>

    <template v-else-if="name === 'admin'">
      <path
        d="M12 3.5 14 6l3-.2.9 2.8 2.6 1.5-1.3 2.7 1.3 2.7-2.6 1.5-.9 2.8-3-.2-2 2.5-2-2.5-3 .2-.9-2.8-2.6-1.5L4.8 13 3.5 10.3 6.1 8.8 7 6l3 .2Z"
      />
      <circle cx="12" cy="13" r="2.7" />
    </template>

    <template v-else-if="name === 'user'">
      <circle cx="12" cy="8.5" r="3.5" />
      <path d="M5 19c1.8-2.7 4.1-4 7-4s5.2 1.3 7 4" />
    </template>

    <template v-else-if="name === 'logout'">
      <path d="M10 6H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h4" />
      <path d="M14 16.5 19 12l-5-4.5" />
      <path d="M9.5 12H19" />
    </template>

    <template v-else-if="name === 'moon'">
      <path d="M17.5 14.5a6.5 6.5 0 0 1-8-8 7.5 7.5 0 1 0 8 8Z" />
    </template>

    <template v-else-if="name === 'sun'">
      <circle cx="12" cy="12" r="3.5" />
      <path d="M12 2.5v2.2" />
      <path d="M12 19.3v2.2" />
      <path d="m4.9 4.9 1.5 1.5" />
      <path d="m17.6 17.6 1.5 1.5" />
      <path d="M2.5 12h2.2" />
      <path d="M19.3 12h2.2" />
      <path d="m4.9 19.1 1.5-1.5" />
      <path d="m17.6 6.4 1.5-1.5" />
    </template>

    <template v-else-if="name === 'globe'">
      <circle cx="12" cy="12" r="8.5" />
      <path d="M3.5 12h17" />
      <path
        d="M12 3.5c2.3 2.2 3.5 5 3.5 8.5S14.3 18.3 12 20.5c-2.3-2.2-3.5-5-3.5-8.5S9.7 5.7 12 3.5Z"
      />
    </template>

    <template v-else-if="name === 'market'">
      <path d="M4 10.5 8.5 6 12 8.5 20 5.5" />
      <path d="M4 18.5h16" />
      <path d="M7 18.5v-4" />
      <path d="M12 18.5v-6" />
      <path d="M17 18.5v-8" />
    </template>

    <template v-else-if="name === 'trend'">
      <path d="M4 17.5 9 12.5l3 2 8-8" />
      <path d="M16 6.5h4v4" />
    </template>

    <template v-else>
      <circle cx="12" cy="12" r="8" />
    </template>
  </svg>
</template>
