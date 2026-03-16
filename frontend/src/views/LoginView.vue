<script setup>
  import { ref } from 'vue'
  import { useRouter } from 'vue-router'
  import { useI18n } from 'vue-i18n'
  import { useAuthStore } from '../stores/auth'

  const { t } = useI18n()
  const auth = useAuthStore()
  const router = useRouter()

  const isLogin = ref(true)
  const email = ref('')
  const password = ref('')
  const fullName = ref('')
  const error = ref('')
  const loading = ref(false)
  const formErrors = ref({})

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
      error.value = e.response?.data?.detail || t('common.error')
    } finally {
      loading.value = false
    }
  }
</script>

<template>
  <div class="login-page">
    <div class="login-card">
      <h1>{{ t('app.title') }}</h1>
      <p>{{ t('app.subtitle') }}</p>

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
          <span v-if="formErrors.fullName" id="fullName-error" class="field-error">{{ formErrors.fullName }}</span>
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
          <span v-if="formErrors.email" id="email-error" class="field-error">{{ formErrors.email }}</span>
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
          <span v-if="formErrors.password" id="password-error" class="field-error">{{ formErrors.password }}</span>
        </div>

        <p v-if="error" class="error" style="margin-bottom: 12px">{{ error }}</p>

        <button type="submit" :disabled="loading">
          {{
            loading
              ? t('common.loading')
              : isLogin
                ? t('auth.loginButton')
                : t('auth.registerButton')
          }}
        </button>
      </form>

      <div class="login-footer">
        <template v-if="isLogin">
          {{ t('auth.noAccount') }}
          <a href="#" @click.prevent="isLogin = false">{{ t('auth.registerButton') }}</a>
        </template>
        <template v-else>
          {{ t('auth.hasAccount') }}
          <a href="#" @click.prevent="isLogin = true">{{ t('auth.loginButton') }}</a>
        </template>
      </div>
    </div>
  </div>
</template>
