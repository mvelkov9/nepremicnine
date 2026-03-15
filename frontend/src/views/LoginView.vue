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

async function handleSubmit() {
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

      <form @submit.prevent="handleSubmit">
        <div v-if="!isLogin" class="field">
          <label>{{ t('auth.fullName') }}</label>
          <input v-model="fullName" type="text" required />
        </div>

        <div class="field">
          <label>{{ t('auth.email') }}</label>
          <input v-model="email" type="email" required autocomplete="username" />
        </div>

        <div class="field">
          <label>{{ t('auth.password') }}</label>
          <input v-model="password" type="password" required autocomplete="current-password" />
        </div>

        <p v-if="error" class="error" style="margin-bottom: 12px">{{ error }}</p>

        <button type="submit" :disabled="loading">
          {{ loading ? t('common.loading') : isLogin ? t('auth.loginButton') : t('auth.registerButton') }}
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
