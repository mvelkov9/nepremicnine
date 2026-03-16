<script setup>
  import Card from 'primevue/card'
  import Button from 'primevue/button'
  import { useI18n } from 'vue-i18n'
  import { RouterLink } from 'vue-router'

  const { t } = useI18n()

  const sections = [
    {
      to: '/admin/podatki',
      title: 'nav.data',
      description: 'layout.page.data',
      icon: 'pi pi-database',
    },
    {
      to: '/admin/priprava',
      title: 'nav.prepare',
      description: 'layout.page.prepare',
      icon: 'pi pi-cog',
    },
    {
      to: '/admin/model',
      title: 'nav.model',
      description: 'layout.page.model',
      icon: 'pi pi-chart-line',
    },
    {
      to: '/admin/diagnostika',
      title: 'nav.diagnostics',
      description: 'layout.page.diagnostics',
      icon: 'pi pi-sliders-h',
    },
    {
      to: '/admin/uporabniki',
      title: 'admin.userManagement',
      description: 'layout.page.adminUsers',
      icon: 'pi pi-users',
    },
  ]
</script>

<template>
  <div class="admin-home">
    <section class="admin-hero">
      <div>
        <p class="eyebrow">{{ t('layout.adminWorkbench') }}</p>
        <h1>{{ t('layout.adminWorkbenchTitle') }}</h1>
        <p class="muted">{{ t('layout.adminWorkbenchBody') }}</p>
      </div>

      <RouterLink to="/" class="hero-link">
        <Button
          severity="contrast"
          outlined
          icon="pi pi-arrow-left"
          :label="t('layout.backToMarket')"
        />
      </RouterLink>
    </section>

    <section class="admin-grid">
      <Card v-for="section in sections" :key="section.to" class="admin-card">
        <template #title>
          <div class="card-title">
            <i :class="section.icon"></i>
            <span>{{ t(section.title) }}</span>
          </div>
        </template>

        <template #content>
          <p class="muted">{{ t(section.description) }}</p>
          <RouterLink :to="section.to">
            <Button icon="pi pi-arrow-right" :label="t('common.open')" />
          </RouterLink>
        </template>
      </Card>
    </section>
  </div>
</template>

<style scoped>
  .admin-home {
    display: grid;
    gap: 1.25rem;
  }

  .admin-hero {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 1rem;
    padding: 1.5rem;
    border: 1px solid var(--border);
    border-radius: 1.5rem;
    background: linear-gradient(135deg, var(--surface-strong), var(--surface-soft));
    box-shadow: var(--shadow-sm);
  }

  .admin-hero h1 {
    margin: 0;
    font-family: var(--font-display);
    font-size: clamp(1.8rem, 4vw, 2.6rem);
  }

  .admin-hero p {
    margin: 0.6rem 0 0;
    max-width: 60ch;
  }

  .hero-link {
    text-decoration: none;
  }

  .admin-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: 1rem;
  }

  .admin-card {
    border-radius: 1.25rem;
  }

  .card-title {
    display: flex;
    align-items: center;
    gap: 0.65rem;
    font-weight: 700;
  }

  .card-title i {
    color: var(--primary);
  }

  @media (max-width: 720px) {
    .admin-hero {
      align-items: stretch;
      flex-direction: column;
    }
  }
</style>
