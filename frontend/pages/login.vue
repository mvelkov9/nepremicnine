<script setup lang="ts">
  definePageMeta({ layout: 'auth', middleware: 'guest' })

  const { t, locale } = useI18n()
  const auth = useAuthStore()
  const route = useRoute()
  const colorMode = useColorMode()
  const toast = useToast()
  const api = useApi()

  const mode = ref<'login' | 'register'>('login')
  const form = reactive({ email: '', password: '', full_name: '' })
  const loading = ref(false)
  const error = ref('')

  const marketCards = computed(() => [
    {
      icon: 'i-lucide-map',
      title: t('auth.marketMap'),
      value: t('auth.marketMapValue'),
      featured: true,
    },
    {
      icon: 'i-lucide-trending-up',
      title: t('auth.marketTrend'),
      value: t('auth.marketTrendValue'),
      featured: false,
    },
    {
      icon: 'i-lucide-bolt',
      title: t('auth.marketEstimate'),
      value: t('auth.marketEstimateValue'),
      featured: false,
    },
  ])

  async function handleLogin() {
    loading.value = true
    error.value = ''
    try {
      await auth.login(form.email, form.password)
      const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
      await navigateTo(redirect)
    } catch (e) {
      error.value = getApiErrorMessage(e, t)
    } finally {
      loading.value = false
    }
  }

  async function handleRegister() {
    loading.value = true
    error.value = ''
    try {
      await api.post('/api/auth/register', {
        email: form.email,
        password: form.password,
        full_name: form.full_name,
      })
      mode.value = 'login'
      form.password = ''
      toast.add({
        title: t('auth.registerSuccess') || 'Account created! Please log in.',
        color: 'success',
        icon: 'i-lucide-check-circle',
      })
    } catch (e) {
      error.value = getApiErrorMessage(e, t)
    } finally {
      loading.value = false
    }
  }

  function handleSubmit() {
    if (mode.value === 'login') {
      handleLogin()
    } else {
      handleRegister()
    }
  }

  function switchLocale(next: 'sl' | 'en') {
    locale.value = next
  }

  function toggleTheme() {
    colorMode.preference = colorMode.value === 'dark' ? 'light' : 'dark'
  }

  function setAuthMode(payload: string | number) {
    mode.value = Number(payload) === 0 ? 'login' : 'register'
    error.value = ''
  }
</script>

<template>
  <div class="page-frame auth-shell py-8 lg:py-12">
    <div class="login-page">
      <!-- Showcase side -->
      <section class="login-showcase">
        <div class="showcase-head">
          <div class="showcase-brand">
            <span class="brand-mark">
              <UIcon name="i-lucide-building-2" class="w-5 h-5" />
            </span>
            <div class="brand-copy">
              <strong>{{ t('app.title') }}</strong>
              <small>{{ t('layout.brandTagline') }}</small>
            </div>
          </div>

          <div>
            <h1>{{ t('auth.welcomeTitle') }}</h1>
            <p>{{ t('auth.welcomeBody') }}</p>
          </div>
        </div>

        <div class="market-grid">
          <article
            v-for="(card, index) in marketCards"
            :key="card.title"
            class="market-card"
            :class="{ featured: index === 0 }"
          >
            <div class="market-card-head">
              <span class="market-icon">
                <UIcon :name="card.icon" class="w-4 h-4" />
              </span>
              <strong>{{ card.title }}</strong>
            </div>
            <p>{{ card.value }}</p>
          </article>
        </div>
      </section>

      <!-- Login/Register panel -->
      <section class="login-panel">
        <div class="login-panel-top">
          <div>
            <p class="eyebrow">{{ t('app.title') }}</p>
            <h2>{{ mode === 'login' ? t('auth.loginButton') : t('auth.registerButton') }}</h2>
            <p class="muted">
              {{ mode === 'login' ? t('auth.noAccount') : t('auth.hasAccount') }}
            </p>
          </div>

          <div class="login-panel-actions">
            <div class="shell-segmented" :aria-label="t('layout.language')">
              <button
                type="button"
                class="shell-segmented-option"
                :class="{ active: locale === 'sl' }"
                @click="switchLocale('sl')"
              >
                SL
              </button>
              <button
                type="button"
                class="shell-segmented-option"
                :class="{ active: locale === 'en' }"
                @click="switchLocale('en')"
              >
                EN
              </button>
            </div>

            <button
              type="button"
              class="shell-icon-button"
              :aria-label="colorMode.value === 'dark' ? t('ui.lightMode') : t('ui.darkMode')"
              @click="toggleTheme"
            >
              <UIcon
                :name="colorMode.value === 'dark' ? 'i-lucide-sun' : 'i-lucide-moon'"
                class="w-4 h-4"
              />
            </button>
          </div>
        </div>

        <!-- Mode switcher -->
        <UTabs
          :items="[
            { label: t('auth.loginButton'), value: 'login' },
            { label: t('auth.registerButton'), value: 'register' },
          ]"
          :model-value="mode === 'login' ? 0 : 1"
          @update:model-value="setAuthMode"
        />

        <!-- Form -->
        <form class="auth-form" novalidate @submit.prevent="handleSubmit">
          <label v-if="mode === 'register'" class="field">
            <span>{{ t('auth.fullName') }}</span>
            <UInput
              v-model="form.full_name"
              type="text"
              :placeholder="t('auth.fullName')"
              autocomplete="name"
              size="xl"
            />
          </label>

          <label class="field">
            <span>{{ t('auth.email') }}</span>
            <UInput
              v-model="form.email"
              type="email"
              :placeholder="t('auth.email')"
              autocomplete="username"
              size="xl"
            />
          </label>

          <label class="field">
            <span>{{ t('auth.password') }}</span>
            <UInput
              v-model="form.password"
              type="password"
              :placeholder="t('auth.password')"
              autocomplete="current-password"
              size="xl"
            />
          </label>

          <UAlert
            v-if="error"
            :description="error"
            color="error"
            variant="soft"
            icon="i-lucide-alert-circle"
            class="auth-error"
          />

          <UButton
            type="submit"
            block
            size="xl"
            :loading="loading"
            :label="
              loading
                ? t('common.loading')
                : mode === 'login'
                  ? t('auth.loginButton')
                  : t('auth.registerButton')
            "
          />
        </form>

        <p class="login-footer">
          {{ mode === 'login' ? t('auth.noAccount') : t('auth.hasAccount') }}
          <UButton
            variant="link"
            size="sm"
            :padded="false"
            @click="
              mode = mode === 'login' ? 'register' : 'login'
              error = ''
            "
          >
            {{ mode === 'login' ? t('auth.registerButton') : t('auth.loginButton') }}
          </UButton>
        </p>
      </section>
    </div>
  </div>
</template>
