<script setup>
  import { computed, ref } from 'vue'
  import { useI18n } from 'vue-i18n'
  import AppIcon from '~/legacy/components/AppIcon.vue'
  import { setLocale } from '~/legacy/i18n'
  import api from '~/legacy/composables/useApi'
  import { useAuthStore } from '~/legacy/stores/auth'
  import { getApiErrorMessage } from '~/legacy/utils/apiError'

  definePageMeta({
    layout: 'auth',
    middleware: ['guest'],
  })

  const route = useRoute()
  const router = useRouter()
  const auth = useAuthStore()
  const colorMode = useColorMode()
  const { t, locale } = useI18n()

  const authMode = ref('login')
  const email = ref('')
  const password = ref('')
  const fullName = ref('')
  const loading = ref(false)
  const error = ref('')

  useSeoMeta({
    title: () => `${t('auth.loginButton')} | ${t('app.title')}`,
    description: () => t('layout.page.login'),
    ogTitle: () => `${t('auth.loginButton')} | ${t('app.title')}`,
    ogDescription: () => t('layout.page.login'),
  })

  const isLogin = computed(() => authMode.value === 'login')
  const authModeItems = computed(() => [
    { label: t('auth.loginButton'), value: 'login' },
    { label: t('auth.registerButton'), value: 'register' },
  ])

  const marketCards = computed(() => [
    {
      icon: 'i-lucide-map',
      title: t('auth.marketMap'),
      value: t('auth.marketMapValue'),
      tone: 'primary',
    },
    {
      icon: 'i-lucide-chart-no-axes-combined',
      title: t('auth.marketTrend'),
      value: t('auth.marketTrendValue'),
      tone: 'secondary',
    },
    {
      icon: 'i-lucide-badge-euro',
      title: t('auth.marketEstimate'),
      value: t('auth.marketEstimateValue'),
      tone: 'success',
    },
  ])

  const platformHighlights = computed(() => [
    t('auth.highlightPrepared'),
    t('auth.highlightModel'),
    t('auth.highlightInsights'),
  ])

  async function submit() {
    loading.value = true
    error.value = ''

    try {
      if (isLogin.value) {
        await auth.login(email.value, password.value)
      } else {
        await api.post('/api/auth/register', {
          email: email.value,
          password: password.value,
          full_name: fullName.value,
        })
        await auth.login(email.value, password.value)
      }

      await router.push(typeof route.query.redirect === 'string' ? route.query.redirect : '/')
    } catch (err) {
      error.value = getApiErrorMessage(err, t)
    } finally {
      loading.value = false
    }
  }

  function switchLocale(nextLocale) {
    locale.value = nextLocale
    setLocale(nextLocale)
  }

  function toggleTheme() {
    colorMode.preference = colorMode.value === 'dark' ? 'light' : 'dark'
  }
</script>

<template>
  <div class="page-frame grid min-h-[calc(100vh-5rem)] items-center py-10 lg:py-14">
    <div class="grid gap-6 xl:grid-cols-[minmax(0,1.2fr)_minmax(24rem,0.85fr)]">
      <UCard
        variant="subtle"
        class="overflow-hidden border border-default/70 bg-gradient-to-br from-default via-elevated to-primary/10 shadow-2xl shadow-primary/10"
      >
        <div class="grid gap-8">
          <div class="flex flex-wrap items-center justify-between gap-4">
            <div class="flex items-center gap-4">
              <span class="flex size-14 items-center justify-center rounded-3xl bg-primary/10 text-primary">
                <AppIcon name="brand" :size="28" />
              </span>
              <div>
                <p class="text-sm font-semibold uppercase tracking-[0.22em] text-muted">
                  {{ t('app.title') }}
                </p>
                <p class="mt-1 text-sm text-toned">
                  {{ t('layout.brandTagline') }}
                </p>
              </div>
            </div>

            <div class="flex items-center gap-2">
              <UButton
                color="neutral"
                :variant="locale === 'sl' ? 'solid' : 'ghost'"
                size="sm"
                @click="switchLocale('sl')"
              >
                SL
              </UButton>
              <UButton
                color="neutral"
                :variant="locale === 'en' ? 'solid' : 'ghost'"
                size="sm"
                @click="switchLocale('en')"
              >
                EN
              </UButton>
              <UButton
                color="neutral"
                variant="ghost"
                :icon="colorMode.value === 'dark' ? 'i-lucide-sun-medium' : 'i-lucide-moon-star'"
                @click="toggleTheme"
              />
            </div>
          </div>

          <div class="grid gap-4">
            <UBadge
              :label="t('auth.welcomeTitle')"
              color="primary"
              variant="soft"
              class="w-fit"
            />
            <div class="grid gap-3">
              <h1 class="max-w-[11ch] text-4xl font-semibold tracking-tight text-highlighted lg:text-5xl">
                {{ t('auth.welcomeTitle') }}
              </h1>
              <p class="max-w-3xl text-sm leading-7 text-muted">
                {{ t('auth.welcomeBody') }}
              </p>
            </div>
          </div>

          <div class="grid gap-4 lg:grid-cols-3">
            <UCard
              v-for="card in marketCards"
              :key="card.title"
              class="border border-default/70 bg-default/85"
            >
              <div class="grid gap-3">
                <div class="flex items-center justify-between gap-3">
                  <div class="flex size-11 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                    <UIcon :name="card.icon" class="size-5" />
                  </div>
                  <UBadge :color="card.tone" variant="soft" class="h-fit" />
                </div>
                <div class="grid gap-2">
                  <h2 class="text-lg font-semibold tracking-tight text-highlighted">
                    {{ card.title }}
                  </h2>
                  <p class="text-sm leading-6 text-muted">
                    {{ card.value }}
                  </p>
                </div>
              </div>
            </UCard>
          </div>

          <div class="grid gap-3 rounded-[1.75rem] border border-default/70 bg-default/85 p-5">
            <div class="flex items-center gap-3">
              <div class="flex size-11 items-center justify-center rounded-2xl bg-secondary/10 text-secondary">
                <UIcon name="i-lucide-orbit" class="size-5" />
              </div>
              <div>
                <p class="text-sm font-semibold text-highlighted">
                  {{ t('layout.workflowHint') }}
                </p>
                <p class="text-sm text-muted">
                  {{ t('dashboard.workflowViewerDetail') }}
                </p>
              </div>
            </div>

            <div class="grid gap-3 sm:grid-cols-3">
              <div
                v-for="highlight in platformHighlights"
                :key="highlight"
                class="rounded-2xl border border-default/70 bg-muted/40 px-4 py-3 text-sm leading-6 text-toned"
              >
                {{ highlight }}
              </div>
            </div>
          </div>
        </div>
      </UCard>

      <UCard class="border border-default/70 bg-default/90 shadow-2xl shadow-black/10">
        <div class="grid gap-6">
          <div class="grid gap-3">
            <p class="text-sm font-semibold uppercase tracking-[0.22em] text-muted">
              {{ t('app.title') }}
            </p>
            <div class="grid gap-2">
              <h2 class="text-3xl font-semibold tracking-tight text-highlighted">
                {{ isLogin ? t('auth.loginButton') : t('auth.registerButton') }}
              </h2>
              <p class="text-sm text-muted">
                {{ isLogin ? t('auth.noAccount') : t('auth.hasAccount') }}
              </p>
            </div>
          </div>

          <UTabs
            v-model="authMode"
            :items="authModeItems"
            value-key="value"
            label-key="label"
            :content="false"
            color="primary"
            variant="link"
          />

          <form class="grid gap-4" @submit.prevent="submit">
            <UInput
              v-if="!isLogin"
              v-model="fullName"
              :placeholder="t('auth.fullName')"
              icon="i-lucide-user-round"
              size="xl"
              color="neutral"
              variant="subtle"
              autocomplete="name"
            />

            <UInput
              v-model="email"
              :placeholder="t('auth.email')"
              icon="i-lucide-mail"
              size="xl"
              color="neutral"
              variant="subtle"
              autocomplete="username"
              type="email"
            />

            <UInput
              v-model="password"
              :placeholder="t('auth.password')"
              icon="i-lucide-key-round"
              size="xl"
              color="neutral"
              variant="subtle"
              autocomplete="current-password"
              type="password"
            />

            <UAlert
              v-if="error"
              color="error"
              variant="soft"
              icon="i-lucide-triangle-alert"
              :title="t('common.error')"
              :description="error"
            />

            <UButton
              type="submit"
              block
              size="xl"
              :loading="loading"
              :icon="isLogin ? 'i-lucide-log-in' : 'i-lucide-user-plus'"
            >
              {{ isLogin ? t('auth.loginButton') : t('auth.registerButton') }}
            </UButton>
          </form>

          <div class="rounded-2xl border border-dashed border-default/80 bg-muted/40 p-4 text-sm text-toned">
            {{ isLogin ? t('auth.noAccount') : t('auth.hasAccount') }}
            <UButton
              color="primary"
              variant="link"
              class="ml-1 px-0"
              @click="authMode = isLogin ? 'register' : 'login'"
            >
              {{ isLogin ? t('auth.registerButton') : t('auth.loginButton') }}
            </UButton>
          </div>
        </div>
      </UCard>
    </div>
  </div>
</template>
