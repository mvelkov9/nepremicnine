<script setup lang="ts">
  import { computed } from 'vue'
  import { RouterLink } from 'vue-router'
  import { useI18n } from 'vue-i18n'
  import Button from 'primevue/button'
  import EmptyState from '../components/EmptyState.vue'
  import PageHeader from '../components/PageHeader.vue'
  import { useAuthStore } from '../stores/auth'

  const { t } = useI18n()
  const auth = useAuthStore()

  const homeRoute = computed(() => (auth.isAdmin ? '/admin' : '/'))
  const homeLabel = computed(() => (auth.isAdmin ? t('nav.admin') : t('nav.dashboard')))
</script>

<template>
  <div class="not-found-page">
    <PageHeader
      :eyebrow="t('error.notFound')"
      :title="t('error.notFound')"
      :description="t('layout.page.dashboard')"
    />

    <section class="panel">
      <EmptyState icon="pi pi-compass" :message="t('error.notFound')">
        <template #actions>
          <RouterLink :to="homeRoute">
            <Button icon="pi pi-home" :label="homeLabel" />
          </RouterLink>
        </template>
      </EmptyState>
    </section>
  </div>
</template>

<style scoped>
  .not-found-page {
    display: grid;
    gap: clamp(1.25rem, 2vw, 1.75rem);
  }

  .panel {
    padding: 0;
    border: none;
    background: transparent;
    box-shadow: none;
  }
</style>
