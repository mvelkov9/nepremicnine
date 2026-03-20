<script setup lang="ts">
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
      <article v-for="section in sections" :key="section.to" class="admin-card">
        <div class="admin-card-head">
          <span class="admin-card-icon">
            <i :class="section.icon"></i>
          </span>
          <div class="admin-card-copy">
            <p class="eyebrow subtle">{{ t('layout.adminWorkbenchShort') }}</p>
            <h2>{{ t(section.title) }}</h2>
          </div>
        </div>

        <p class="muted">{{ t(section.description) }}</p>

        <RouterLink :to="section.to" class="admin-card-link">
          <Button icon="pi pi-arrow-right" :label="t('common.open')" />
        </RouterLink>
      </article>
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
    display: grid;
    gap: 1rem;
    padding: 1.2rem;
    border-radius: 1.45rem;
    border: 1px solid var(--border);
    background:
      linear-gradient(180deg, rgb(255 255 255 / 24%), transparent 32%),
      color-mix(in srgb, var(--surface-soft) 86%, var(--primary) 14%);
    box-shadow: var(--shadow-sm);
  }

  .admin-card-head {
    display: flex;
    align-items: flex-start;
    gap: 0.9rem;
  }

  .admin-card-icon {
    width: 2.9rem;
    height: 2.9rem;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    border-radius: 1rem;
    background: linear-gradient(145deg, var(--primary), var(--secondary));
    color: var(--primary-contrast);
    box-shadow: 0 18px 34px rgb(45 132 121 / 24%);
  }

  .admin-card-copy {
    display: grid;
    gap: 0.35rem;
  }

  .admin-card-copy h2 {
    margin: 0;
    font-family: var(--font-display);
    font-size: 1.25rem;
    line-height: 1.05;
  }

  .admin-card-link {
    text-decoration: none;
  }

  .eyebrow.subtle {
    color: var(--text-soft);
  }

  @media (max-width: 720px) {
    .admin-hero {
      align-items: stretch;
      flex-direction: column;
    }
  }
</style>
