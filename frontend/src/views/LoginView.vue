<script setup lang="ts">
  import { computed, ref, watch } from 'vue'
  import { useRoute, useRouter } from 'vue-router'
  import { useI18n } from 'vue-i18n'
  import AuthShowcase from '../components/auth/AuthShowcase.vue'
  import SectionPanel from '../components/SectionPanel.vue'
  import { setLocale } from '../i18n'
  import { useAuthStore } from '../stores/auth'
  import { getApiErrorMessage } from '../utils/apiError'

  const { t, locale } = useI18n()
  const auth = useAuthStore()
  const route = useRoute()
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

  const panelDescription = computed(() =>
    isLogin.value ? t('layout.page.login') : t('auth.registerBody'),
  )

  const fallbackRoute = computed(() => (auth.isAdmin ? '/admin' : '/'))

  function resolveRedirectTarget() {
    const raw = typeof route.query.redirect === 'string' ? route.query.redirect : ''
    if (!raw || !raw.startsWith('/')) return fallbackRoute.value
    return raw.startsWith('//') ? fallbackRoute.value : raw
  }

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
      await router.replace(resolveRedirectTarget())
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

  watch(isLogin, () => {
    error.value = ''
    formErrors.value = {}
    if (isLogin.value) return
    password.value = ''
  })
</script>

<template>
  <main id="guest-main-content" class="auth-page">
    <AuthShowcase class="auth-page__showcase" />

    <SectionPanel
      tag="section"
      class="auth-page__panel"
      :eyebrow="t('app.title')"
      :title="isLogin ? t('auth.loginButton') : t('auth.registerButton')"
    >
      <template #actions>
        <SelectButton
          :model-value="locale"
          :options="localeOptions"
          option-label="label"
          option-value="value"
          :aria-label="t('layout.language')"
          @update:model-value="onLocaleChange"
        />
      </template>

      <p class="auth-panel-copy">{{ panelDescription }}</p>

      <div
        class="auth-mode-switch"
        role="group"
        :aria-label="`${t('auth.loginButton')} / ${t('auth.registerButton')}`"
      >
        <button
          type="button"
          class="auth-mode-switch__option"
          :class="{ 'is-active': isLogin }"
          :aria-pressed="isLogin"
          @click="isLogin = true"
        >
          {{ t('auth.loginButton') }}
        </button>
        <button
          type="button"
          class="auth-mode-switch__option"
          :class="{ 'is-active': !isLogin }"
          :aria-pressed="!isLogin"
          @click="isLogin = false"
        >
          {{ t('auth.registerButton') }}
        </button>
      </div>

      <form @submit.prevent="handleSubmit" novalidate class="auth-form">
        <div v-if="!isLogin" class="field">
          <label for="fullName">{{ t('auth.fullName') }}</label>
          <InputText
            id="fullName"
            v-model="fullName"
            autocomplete="name"
            :invalid="!!formErrors.fullName"
            :aria-describedby="formErrors.fullName ? 'fullName-error' : undefined"
            @input="formErrors.fullName = null"
          />
          <small v-if="formErrors.fullName" id="fullName-error" class="field-error">
            {{ formErrors.fullName }}
          </small>
        </div>

        <div class="field">
          <label for="email">{{ t('auth.email') }}</label>
          <InputText
            id="email"
            v-model="email"
            type="email"
            data-testid="email-input"
            autocomplete="username"
            :invalid="!!formErrors.email"
            :aria-describedby="formErrors.email ? 'email-error' : undefined"
            @input="formErrors.email = null"
          />
          <small v-if="formErrors.email" id="email-error" class="field-error">
            {{ formErrors.email }}
          </small>
        </div>

        <div class="field">
          <label for="password">{{ t('auth.password') }}</label>
          <Password
            id="password"
            v-model="password"
            input-class="password-input"
            :feedback="false"
            toggle-mask
            input-id="password"
            :autocomplete="isLogin ? 'current-password' : 'new-password'"
            :invalid="!!formErrors.password"
            :aria-describedby="formErrors.password ? 'password-error' : undefined"
            @input="formErrors.password = null"
          />
          <small v-if="formErrors.password" id="password-error" class="field-error">
            {{ formErrors.password }}
          </small>
        </div>

        <div v-if="error" class="auth-alert" role="alert" aria-live="polite">
          <span class="auth-alert__icon">
            <i class="pi pi-exclamation-triangle" aria-hidden="true"></i>
          </span>
          <div class="auth-alert__copy">
            <strong>{{ isLogin ? t('auth.loginButton') : t('auth.registerButton') }}</strong>
            <p>{{ error }}</p>
          </div>
        </div>

        <Button
          type="submit"
          data-testid="login-button"
          :loading="loading"
          :icon="isLogin ? 'pi pi-sign-in' : 'pi pi-user-plus'"
          :label="isLogin ? t('auth.loginButton') : t('auth.registerButton')"
          class="auth-submit"
        />
      </form>

      <p class="auth-footer">
        {{ isLogin ? t('auth.noAccount') : t('auth.hasAccount') }}
        <Button
          :label="isLogin ? t('auth.registerButton') : t('auth.loginButton')"
          link
          class="inline-switch-btn"
          @click="isLogin = !isLogin"
        />
      </p>
    </SectionPanel>
  </main>
</template>

<style scoped>
  #guest-main-content.auth-page {
    position: relative;
    isolation: isolate;
    overflow: clip;
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(23rem, 31rem);
    align-items: stretch;
    gap: clamp(1rem, 2vw, 1.4rem);
    max-width: 70rem;
    margin: 0 auto;
    padding: clamp(1.25rem, 4vw, 3rem) 1rem;
  }

  #guest-main-content.auth-page::before,
  #guest-main-content.auth-page::after {
    content: '';
    position: absolute;
    inset: auto;
    z-index: -1;
    border-radius: 999px;
    filter: blur(56px);
    opacity: 0.85;
    pointer-events: none;
  }

  #guest-main-content.auth-page::before {
    top: -5rem;
    right: -3rem;
    width: 18rem;
    height: 18rem;
    background: color-mix(in srgb, var(--primary) 14%, transparent);
  }

  #guest-main-content.auth-page::after {
    bottom: -5rem;
    left: -3rem;
    width: 18rem;
    height: 18rem;
    background: color-mix(in srgb, var(--secondary) 12%, transparent);
  }

  #guest-main-content.auth-page .auth-page__showcase,
  #guest-main-content.auth-page .auth-page__panel {
    min-width: 0;
    width: 100%;
  }

  #guest-main-content.auth-page .auth-page__panel {
    max-width: 31rem;
    justify-self: end;
    align-self: stretch;
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface-card-strong) 97%, transparent),
        transparent 130%
      ),
      var(--surface-panel);
    box-shadow:
      inset 0 1px 0 var(--content-glow),
      var(--shadow-lg);
  }

  #guest-main-content.auth-page .auth-page__panel :deep(.panel-head) {
    align-items: center;
    gap: 0.9rem;
  }

  #guest-main-content.auth-page .auth-page__panel :deep(.panel-head h2) {
    font-size: clamp(1.35rem, 2.6vw, 1.7rem);
    line-height: 1.02;
  }

  #guest-main-content.auth-page .auth-page__panel :deep(.panel-head .p-selectbutton) {
    display: inline-grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.22rem;
    padding: 0.2rem;
    border-radius: 999px;
    border: 1px solid color-mix(in srgb, var(--border) 74%, var(--content-border-strong) 26%);
    background: color-mix(in srgb, var(--surface-card-strong) 94%, transparent);
  }

  #guest-main-content.auth-page .auth-page__panel :deep(.panel-head .p-togglebutton) {
    min-width: 2.75rem;
    min-height: 2rem;
    border-radius: 999px;
  }

  #guest-main-content.auth-page .auth-page__panel :deep(.panel-head .p-togglebutton-label) {
    font-size: 0.72rem;
    letter-spacing: 0.08em;
  }

  #guest-main-content.auth-page .auth-panel-copy {
    margin: 0 0 0.15rem;
    max-width: 30ch;
    color: var(--text-soft);
    font-size: 0.88rem;
    line-height: 1.52;
  }

  #guest-main-content.auth-page .auth-mode-switch {
    display: inline-grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.25rem;
    width: fit-content;
    max-width: 100%;
    margin-bottom: 0.6rem;
    padding: 0.24rem;
    border: 1px solid color-mix(in srgb, var(--border) 70%, var(--content-border-strong) 30%);
    border-radius: 999px;
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--primary-overlay) 16%, transparent),
        transparent 45%
      ),
      color-mix(in srgb, var(--surface-card-strong) 92%, transparent);
    box-shadow:
      inset 0 1px 0 var(--content-glow),
      0 10px 22px color-mix(in srgb, rgb(2 6 23) 6%, transparent);
  }

  #guest-main-content.auth-page .auth-mode-switch__option {
    appearance: none;
    border: 0;
    min-width: 7.5rem;
    min-height: 2.2rem;
    padding: 0.48rem 0.9rem;
    border-radius: 999px;
    background: transparent;
    color: var(--text-soft);
    font-size: 0.84rem;
    font-weight: 800;
    letter-spacing: 0.01em;
    cursor: pointer;
    transition:
      background 140ms ease,
      color 140ms ease,
      box-shadow 140ms ease,
      transform 140ms ease;
  }

  #guest-main-content.auth-page .auth-mode-switch__option:hover {
    color: var(--text);
    transform: translateY(-1px);
  }

  #guest-main-content.auth-page .auth-mode-switch__option.is-active {
    background: linear-gradient(
      135deg,
      color-mix(in srgb, var(--primary) 18%, var(--surface-card-strong)),
      color-mix(in srgb, var(--secondary) 12%, var(--surface-card-strong))
    );
    color: var(--text);
    box-shadow:
      inset 0 1px 0 color-mix(in srgb, white 18%, transparent),
      0 8px 18px color-mix(in srgb, rgb(2 6 23) 10%, transparent);
  }

  #guest-main-content.auth-page .auth-form {
    display: grid;
    gap: 0.9rem;
  }

  #guest-main-content.auth-page .auth-form :deep(.p-password),
  #guest-main-content.auth-page .auth-form :deep(.p-password-input) {
    width: 100%;
  }

  #guest-main-content.auth-page .auth-form :deep(.p-inputtext),
  #guest-main-content.auth-page .auth-form :deep(.p-password-input) {
    min-height: 2.85rem;
    padding-inline: 0.92rem;
    border: 1px solid color-mix(in srgb, var(--border) 78%, var(--content-border-strong) 22%);
    border-radius: 0.9rem;
    background: var(--surface-card-strong);
    box-shadow:
      inset 0 1px 0 var(--content-glow),
      0 1px 0 color-mix(in srgb, var(--surface-card-strong) 94%, transparent);
  }

  #guest-main-content.auth-page .auth-form :deep(.p-inputtext:enabled:focus),
  #guest-main-content.auth-page .auth-form :deep(.p-password-input:enabled:focus) {
    border-color: color-mix(in srgb, var(--primary) 46%, transparent);
    box-shadow:
      0 0 0 0.18rem color-mix(in srgb, var(--primary) 12%, transparent),
      inset 0 1px 0 var(--content-glow);
  }

  #guest-main-content.auth-page .field {
    display: grid;
    gap: 0.36rem;
  }

  #guest-main-content.auth-page .field label {
    font-weight: 700;
    color: var(--text-soft);
    font-size: 0.74rem;
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }

  #guest-main-content.auth-page .auth-alert {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 0.8rem;
    align-items: start;
    padding: 0.95rem 1rem;
    border-radius: 1rem;
    border: 1px solid color-mix(in srgb, var(--danger) 28%, var(--border) 72%);
    background:
      linear-gradient(180deg, color-mix(in srgb, var(--danger) 10%, transparent), transparent 46%),
      color-mix(in srgb, var(--surface-card-strong) 96%, var(--danger) 4%);
    box-shadow:
      inset 0 1px 0 var(--content-glow),
      0 10px 22px color-mix(in srgb, var(--danger) 10%, transparent);
  }

  #guest-main-content.auth-page .auth-alert__icon {
    display: inline-grid;
    place-items: center;
    width: 2rem;
    height: 2rem;
    border-radius: 999px;
    background: color-mix(in srgb, var(--danger) 18%, transparent);
    color: var(--danger);
    box-shadow: inset 0 1px 0 color-mix(in srgb, white 18%, transparent);
  }

  #guest-main-content.auth-page .auth-alert__copy {
    display: grid;
    gap: 0.18rem;
  }

  #guest-main-content.auth-page .auth-alert__copy strong {
    color: var(--text);
    font-size: 0.9rem;
  }

  #guest-main-content.auth-page .auth-alert__copy p {
    margin: 0;
    color: var(--text-soft);
    line-height: 1.5;
  }

  #guest-main-content.auth-page .auth-submit {
    width: 100%;
    min-height: 2.9rem;
    margin-top: 0.2rem;
    border-radius: 0.95rem;
    background: linear-gradient(
      135deg,
      color-mix(in srgb, var(--primary) 82%, white 18%),
      color-mix(in srgb, var(--secondary) 72%, var(--primary) 28%)
    );
    box-shadow:
      0 16px 30px color-mix(in srgb, rgb(2 6 23) 18%, transparent),
      inset 0 1px 0 color-mix(in srgb, white 24%, transparent);
  }

  #guest-main-content.auth-page .auth-submit:hover {
    transform: translateY(-1px);
    filter: saturate(1.05);
  }

  #guest-main-content.auth-page .auth-footer {
    margin: 0.9rem 0 0;
    color: var(--text-muted);
    font-size: 0.88rem;
  }

  #guest-main-content.auth-page .inline-switch-btn {
    padding: 0;
    margin-left: 0.3rem;
    font-weight: 800;
  }

  #guest-main-content.auth-page :deep(.p-button) {
    min-height: 2.8rem;
  }

  #guest-main-content.auth-page :deep(.p-button.p-button-link) {
    min-height: unset;
    padding-inline: 0.2rem;
  }

  @media (max-width: 720px) {
    #guest-main-content.auth-page {
      max-width: 100%;
      padding-inline: 0.8rem;
    }

    #guest-main-content.auth-page .auth-page__panel {
      max-width: none;
    }

    #guest-main-content.auth-page .auth-mode-switch {
      width: 100%;
    }

    #guest-main-content.auth-page .auth-mode-switch__option {
      min-width: 0;
      width: 100%;
    }

    #guest-main-content.auth-page .auth-submit,
    #guest-main-content.auth-page :deep(.p-button) {
      min-height: 2.85rem;
    }
  }

  @media (min-width: 721px) and (max-width: 1120px) {
    #guest-main-content.auth-page {
      grid-template-columns: 1fr;
      max-width: 36rem;
    }

    #guest-main-content.auth-page .auth-page__showcase {
      display: none;
    }

    #guest-main-content.auth-page .auth-page__panel {
      justify-self: stretch;
      max-width: none;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    #guest-main-content.auth-page .auth-submit {
      transition: none;
    }

    #guest-main-content.auth-page .auth-submit:hover {
      transform: none;
    }
  }
</style>
