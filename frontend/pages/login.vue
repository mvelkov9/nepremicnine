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

  const isLogin = ref(true)
  const email = ref('')
  const password = ref('')
  const fullName = ref('')
  const loading = ref(false)
  const error = ref('')

  const marketCards = computed(() => [
    { icon: 'map', title: t('auth.marketMap'), value: t('auth.marketMapValue') },
    { icon: 'trend', title: t('auth.marketTrend'), value: t('auth.marketTrendValue') },
    { icon: 'prediction', title: t('auth.marketEstimate'), value: t('auth.marketEstimateValue') },
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
  <div class="page-frame auth-shell py-8 lg:py-12">
    <div class="login-page">
      <section class="login-showcase">
        <div class="showcase-head">
          <div class="showcase-brand">
            <span class="brand-mark">
              <AppIcon name="brand" :size="24" />
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
                <AppIcon :name="card.icon" :size="18" />
              </span>
              <strong>{{ card.title }}</strong>
            </div>
            <p>{{ card.value }}</p>
          </article>
        </div>
      </section>

      <section class="login-panel">
        <div class="login-panel-top">
          <div>
            <p class="eyebrow">{{ t('app.title') }}</p>
            <h2>{{ isLogin ? t('auth.loginButton') : t('auth.registerButton') }}</h2>
            <p class="muted">
              {{ isLogin ? t('auth.noAccount') : t('auth.hasAccount') }}
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
              <AppIcon :name="colorMode.value === 'dark' ? 'sun' : 'moon'" :size="16" />
            </button>
          </div>
        </div>

        <div class="auth-switch">
          <button
            type="button"
            class="auth-switch-btn"
            :class="{ active: isLogin }"
            @click="isLogin = true"
          >
            {{ t('auth.loginButton') }}
          </button>
          <button
            type="button"
            class="auth-switch-btn"
            :class="{ active: !isLogin }"
            @click="isLogin = false"
          >
            {{ t('auth.registerButton') }}
          </button>
        </div>

        <form class="auth-form" @submit.prevent="submit">
          <label v-if="!isLogin" class="field">
            <span>{{ t('auth.fullName') }}</span>
            <input
              v-model="fullName"
              type="text"
              class="form-input"
              autocomplete="name"
            />
          </label>

          <label class="field">
            <span>{{ t('auth.email') }}</span>
            <input
              v-model="email"
              type="email"
              class="form-input"
              autocomplete="username"
            />
          </label>

          <label class="field">
            <span>{{ t('auth.password') }}</span>
            <input
              v-model="password"
              type="password"
              class="form-input"
              autocomplete="current-password"
            />
          </label>

          <p v-if="error" class="error-text auth-error">{{ error }}</p>

          <UButton type="submit" block size="xl" :loading="loading">
            {{ isLogin ? t('auth.loginButton') : t('auth.registerButton') }}
          </UButton>
        </form>

        <p class="login-footer">
          {{ isLogin ? t('auth.noAccount') : t('auth.hasAccount') }}
          <button type="button" class="inline-link" @click="isLogin = !isLogin">
            {{ isLogin ? t('auth.registerButton') : t('auth.loginButton') }}
          </button>
        </p>
      </section>
    </div>
  </div>
</template>
