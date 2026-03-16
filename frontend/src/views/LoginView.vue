<script setup>
  import { computed, ref } from 'vue'
  import { useRouter } from 'vue-router'
  import { useI18n } from 'vue-i18n'
  import { setLocale } from '../i18n'
  import { useAuthStore } from '../stores/auth'
  import { getApiErrorMessage } from '../utils/apiError'

  const { t, locale } = useI18n()
  const auth = useAuthStore()
  const router = useRouter()

  const isLogin = ref(true)
  const email = ref('')
  const password = ref('')
  const fullName = ref('')
  const error = ref('')
  const loading = ref(false)
  const formErrors = ref({})

  const highlights = computed(() => [
    t('auth.highlightPrepared'),
    t('auth.highlightModel'),
    t('auth.highlightInsights'),
  ])

  function validateForm() {
    const errors = {}
    if (!email.value.trim()) errors.email = t('validation.required')
    if (!password.value) errors.password = t('validation.required')
    if (!isLogin.value && !fullName.value.trim()) errors.fullName = t('validation.required')
    formErrors.value = errors
    return Object.keys(errors).length === 0
  }

  async function handleSubmit() {
    if (!validateForm()) return
    error.value = ''
    loading.value = true
    try {
      if (isLogin.value) {
        await auth.login(email.value, password.value)
      } else {
        const api = (await import('../composables/useApi')).default
        await api.post('/api/auth/register', {
          email: email.value,
          password: password.value,
          full_name: fullName.value,
        })
        await auth.login(email.value, password.value)
      }
      router.push('/')
    } catch (e) {
      error.value = getApiErrorMessage(e, t)
    } finally {
      loading.value = false
    }
  }

  function changeLocale(nextLocale) {
    locale.value = nextLocale
    setLocale(nextLocale)
  }
</script>

<template>
  <div class="login-page">
    <section class="login-showcase">
      <div class="showcase-chip">{{ t('app.subtitle') }}</div>
      <h1>{{ t('auth.welcomeTitle') }}</h1>
      <p>{{ t('auth.welcomeBody') }}</p>

      <div class="showcase-grid">
        <article v-for="item in highlights" :key="item" class="showcase-card">
          <span class="showcase-dot"></span>
          <p>{{ item }}</p>
        </article>
      </div>
    </section>

    <section class="login-panel">
      <div class="login-panel-top">
        <div>
          <p class="eyebrow">{{ t('app.title') }}</p>
          <h2>{{ isLogin ? t('auth.loginButton') : t('auth.registerButton') }}</h2>
        </div>

        <div class="segmented-control" role="group" :aria-label="t('layout.language')">
          <button
            class="segmented-btn"
            :class="{ active: locale === 'sl' }"
            @click="changeLocale('sl')"
          >
            SI
          </button>
          <button
            class="segmented-btn"
            :class="{ active: locale === 'en' }"
            @click="changeLocale('en')"
          >
            EN
          </button>
        </div>
      </div>

      <div class="auth-switch">
        <button class="auth-switch-btn" :class="{ active: isLogin }" @click="isLogin = true">
          {{ t('auth.loginButton') }}
        </button>
        <button class="auth-switch-btn" :class="{ active: !isLogin }" @click="isLogin = false">
          {{ t('auth.registerButton') }}
        </button>
      </div>

      <form @submit.prevent="handleSubmit" novalidate>
        <div v-if="!isLogin" class="field">
          <label for="fullName">{{ t('auth.fullName') }}</label>
          <input
            id="fullName"
            v-model="fullName"
            type="text"
            required
            :class="{ 'input-error': formErrors.fullName }"
            :aria-describedby="formErrors.fullName ? 'fullName-error' : undefined"
            @input="formErrors.fullName = null"
          />
          <span v-if="formErrors.fullName" id="fullName-error" class="field-error">{{
            formErrors.fullName
          }}</span>
        </div>

        <div class="field">
          <label for="email">{{ t('auth.email') }}</label>
          <input
            id="email"
            v-model="email"
            type="email"
            required
            autocomplete="username"
            :class="{ 'input-error': formErrors.email }"
            :aria-describedby="formErrors.email ? 'email-error' : undefined"
            @input="formErrors.email = null"
          />
          <span v-if="formErrors.email" id="email-error" class="field-error">{{
            formErrors.email
          }}</span>
        </div>

        <div class="field">
          <label for="password">{{ t('auth.password') }}</label>
          <input
            id="password"
            v-model="password"
            type="password"
            required
            autocomplete="current-password"
            :class="{ 'input-error': formErrors.password }"
            :aria-describedby="formErrors.password ? 'password-error' : undefined"
            @input="formErrors.password = null"
          />
          <span v-if="formErrors.password" id="password-error" class="field-error">{{
            formErrors.password
          }}</span>
        </div>

        <p v-if="error" class="error-text" style="margin-bottom: 0.9rem">{{ error }}</p>

        <button type="submit" class="btn btn-primary auth-submit" :disabled="loading">
          {{
            loading
              ? t('common.loading')
              : isLogin
                ? t('auth.loginButton')
                : t('auth.registerButton')
          }}
        </button>
      </form>

      <p class="login-footer">
        {{ isLogin ? t('auth.noAccount') : t('auth.hasAccount') }}
        <button class="inline-link" @click="isLogin = !isLogin">
          {{ isLogin ? t('auth.registerButton') : t('auth.loginButton') }}
        </button>
      </p>
    </section>
  </div>
</template>
