<script setup lang="ts">
  import { computed, ref } from 'vue'
  import { useRouter } from 'vue-router'
  import { useI18n } from 'vue-i18n'
  import AppIcon from '../components/AppIcon.vue'
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
  const formErrors = ref<Record<string, string | null>>({})

  const localeOptions = [
    { label: 'SI', value: 'sl' },
    { label: 'EN', value: 'en' },
  ]

  const authModeOptions = computed(() => [
    { label: t('auth.loginButton'), value: true },
    { label: t('auth.registerButton'), value: false },
  ])

  const marketCards = computed(() => [
    { icon: 'map', title: t('auth.marketMap'), value: t('auth.marketMapValue') },
    { icon: 'trend', title: t('auth.marketTrend'), value: t('auth.marketTrendValue') },
    { icon: 'prediction', title: t('auth.marketEstimate'), value: t('auth.marketEstimateValue') },
  ])

  function validateForm(): boolean {
    const errors: Record<string, string> = {}
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

  function onLocaleChange(val: string) {
    locale.value = val
    setLocale(val)
  }
</script>

<template>
  <div class="login-page">
    <section class="login-showcase">
      <div class="showcase-chip">{{ t('app.subtitle') }}</div>

      <div class="showcase-head">
        <h1>{{ t('auth.welcomeTitle') }}</h1>
        <p>{{ t('auth.welcomeBody') }}</p>
      </div>

      <div class="showcase-band">
        <span>{{ t('auth.marketBandMap') }}</span>
        <span>{{ t('auth.marketBandTrend') }}</span>
        <span>{{ t('auth.marketBandEstimate') }}</span>
      </div>

      <div class="market-grid">
        <article v-for="card in marketCards" :key="card.title" class="market-card">
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
        </div>

        <SelectButton
          :model-value="locale"
          :options="localeOptions"
          option-label="label"
          option-value="value"
          :aria-label="t('layout.language')"
          @update:model-value="onLocaleChange"
        />
      </div>

      <SelectButton
        v-model="isLogin"
        :options="authModeOptions"
        option-label="label"
        option-value="value"
        class="auth-mode-switch"
      />

      <form @submit.prevent="handleSubmit" novalidate class="login-form">
        <div v-if="!isLogin" class="field">
          <label for="fullName">{{ t('auth.fullName') }}</label>
          <InputText
            id="fullName"
            v-model="fullName"
            :invalid="!!formErrors.fullName"
            :aria-describedby="formErrors.fullName ? 'fullName-error' : undefined"
            @input="formErrors.fullName = null"
          />
          <small v-if="formErrors.fullName" id="fullName-error" class="text-red-500">
            {{ formErrors.fullName }}
          </small>
        </div>

        <div class="field">
          <label for="email">{{ t('auth.email') }}</label>
          <InputText
            id="email"
            v-model="email"
            type="email"
            autocomplete="username"
            :invalid="!!formErrors.email"
            :aria-describedby="formErrors.email ? 'email-error' : undefined"
            @input="formErrors.email = null"
          />
          <small v-if="formErrors.email" id="email-error" class="text-red-500">
            {{ formErrors.email }}
          </small>
        </div>

        <div class="field">
          <label for="password">{{ t('auth.password') }}</label>
          <Password
            id="password"
            v-model="password"
            :feedback="false"
            toggle-mask
            input-id="password"
            autocomplete="current-password"
            :invalid="!!formErrors.password"
            :aria-describedby="formErrors.password ? 'password-error' : undefined"
            @input="formErrors.password = null"
          />
          <small v-if="formErrors.password" id="password-error" class="text-red-500">
            {{ formErrors.password }}
          </small>
        </div>

        <Message v-if="error" severity="error" :closable="false" class="login-error">
          {{ error }}
        </Message>

        <Button
          type="submit"
          :loading="loading"
          :label="isLogin ? t('auth.loginButton') : t('auth.registerButton')"
          class="auth-submit"
        />
      </form>

      <p class="login-footer">
        {{ isLogin ? t('auth.noAccount') : t('auth.hasAccount') }}
        <Button
          :label="isLogin ? t('auth.registerButton') : t('auth.loginButton')"
          link
          class="inline-switch-btn"
          @click="isLogin = !isLogin"
        />
      </p>
    </section>
  </div>
</template>

<style scoped>
  .auth-mode-switch {
    margin-bottom: 1.1rem;
  }

  .auth-mode-switch :deep(.p-togglebutton) {
    flex: 1;
    justify-content: center;
  }

  .login-form {
    display: grid;
    gap: 0.9rem;
  }

  .login-form :deep(.p-password) {
    width: 100%;
  }

  .login-form :deep(.p-password-input) {
    width: 100%;
  }

  .auth-submit {
    width: 100%;
    margin-top: 0.25rem;
  }

  .login-error {
    margin: 0;
  }

  .inline-switch-btn {
    padding: 0;
    margin-left: 0.3rem;
    font-weight: 800;
  }
</style>
