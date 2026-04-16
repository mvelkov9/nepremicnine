<script setup lang="ts">
  import { computed, ref, watch } from 'vue'
  import { RouterLink, useRoute, useRouter } from 'vue-router'
  import { useI18n } from 'vue-i18n'
  import { setLocale } from '../../i18n'
  import { useDarkMode } from '../../composables/useDarkMode'
  import { useAuthStore } from '../../stores/auth'
  import { useToast } from '../../composables/useToast'
  import { getApiErrorMessage } from '../../utils/apiError'

  const visible = defineModel<boolean>('visible', { default: false })

  const { t, locale } = useI18n()
  const auth = useAuthStore()
  const route = useRoute()
  const router = useRouter()
  const { showToast } = useToast()
  const { isDark, toggleDark } = useDarkMode()

  const profileSaving = ref(false)
  const profileForm = ref({
    full_name: '',
    avatar_url: '',
  })

  const localeOptions = [
    { label: 'SL', value: 'sl' },
    { label: 'EN', value: 'en' },
  ]

  const avatarUrl = computed(() => auth.user?.avatar_url || '')
  const profileAvatarUrl = computed(() => profileForm.value.avatar_url.trim() || avatarUrl.value)
  const profileEmail = computed(() => auth.user?.email || t('layout.profilePlaceholder'))
  const profileRole = computed(() =>
    auth.isAdmin ? t('layout.roleAdmin') : t('layout.roleViewer'),
  )
  const themeLabel = computed(() => (isDark.value ? t('ui.darkMode') : t('ui.lightMode')))
  const themeDescription = computed(() => t('ui.toggleTheme'))

  const profileInitials = computed(() => {
    const source = profileForm.value.full_name || auth.user?.full_name || ''
    if (!source.trim()) return '?'
    return source
      .split(' ')
      .map((part: string) => part[0])
      .join('')
      .toUpperCase()
      .slice(0, 2)
  })
  const localeChoice = computed({
    get: () => locale.value,
    set: (nextLocale: string) => changeLocale(nextLocale),
  })
  const switchLink = computed(() => {
    if (!auth.isAdmin) return null

    return route.path.startsWith('/admin')
      ? { to: '/', label: t('layout.backToMarket') }
      : { to: '/admin', label: t('layout.openAdminWorkbench') }
  })

  watch(visible, (open) => {
    if (open) {
      profileForm.value = {
        full_name: auth.user?.full_name || '',
        avatar_url: auth.user?.avatar_url || '',
      }
    }
  })

  async function saveProfile() {
    profileSaving.value = true
    try {
      await auth.updateProfile({
        full_name: profileForm.value.full_name,
        avatar_url: profileForm.value.avatar_url || null,
      })
      showToast(t('layout.profileSaved'), 'success')
      visible.value = false
    } catch (error) {
      showToast(getApiErrorMessage(error, t), 'error')
    } finally {
      profileSaving.value = false
    }
  }

  function changeLocale(nextLocale: string) {
    if (!nextLocale || nextLocale === locale.value) return
    locale.value = nextLocale
    setLocale(nextLocale)
  }

  async function logout() {
    await auth.logout()
    visible.value = false
    router.push('/login')
  }
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="t('layout.profileTitle')"
    class="profile-dialog"
    :dismissable-mask="true"
    :draggable="false"
  >
    <div class="profile-dialog-body">
      <div class="profile-preview">
        <span class="avatar-frame large">
          <img
            v-if="profileAvatarUrl"
            :src="profileAvatarUrl"
            :alt="profileForm.full_name || t('layout.profile')"
          />
          <span v-else>{{ profileInitials }}</span>
        </span>

        <div class="profile-preview-copy">
          <strong>{{ profileForm.full_name || t('layout.profilePlaceholder') }}</strong>
          <p>{{ profileEmail }}</p>
          <small>{{ t('layout.profileDescription') }}</small>
          <div class="profile-preview-badges">
            <span class="profile-badge">{{ profileRole }}</span>
            <span class="profile-badge">{{ themeLabel }}</span>
          </div>
        </div>
      </div>

      <div class="profile-form-grid">
        <label class="profile-field">
          <span>{{ t('auth.fullName') }}</span>
          <InputText v-model="profileForm.full_name" />
        </label>

        <label class="profile-field">
          <span>{{ t('layout.avatarUrl') }}</span>
          <InputText
            v-model="profileForm.avatar_url"
            :placeholder="t('layout.avatarPlaceholder')"
          />
        </label>
      </div>

      <div class="profile-identity-row">
        <div class="identity-block">
          <span>{{ t('layout.profile') }}</span>
          <strong>{{ profileEmail }}</strong>
        </div>
        <div class="identity-block">
          <span>{{ t('layout.language') }}</span>
          <strong>{{ localeChoice === 'sl' ? 'SL' : 'EN' }}</strong>
        </div>
        <div class="identity-block">
          <span>{{ t('ui.toggleTheme') }}</span>
          <strong>{{ themeLabel }}</strong>
        </div>
      </div>

      <div class="profile-preferences">
        <div class="preference-row">
          <div>
            <strong>{{ t('layout.language') }}</strong>
            <p>{{ t('layout.workflowHint') }}</p>
          </div>
          <SelectButton
            v-model="localeChoice"
            :options="localeOptions"
            option-label="label"
            option-value="value"
            :allow-empty="false"
            :aria-label="t('layout.language')"
          />
        </div>

        <div class="preference-row">
          <div>
            <strong>{{ themeLabel }}</strong>
            <p>{{ themeDescription }}</p>
          </div>
          <Button
            severity="secondary"
            outlined
            :icon="isDark ? 'pi pi-moon' : 'pi pi-sun'"
            :label="isDark ? t('ui.lightMode') : t('ui.darkMode')"
            @click="() => toggleDark()"
          />
        </div>

        <div class="profile-secondary-actions">
          <Button
            v-if="switchLink"
            :as="RouterLink"
            :to="switchLink.to"
            class="profile-link-action"
            severity="secondary"
            text
            icon="pi pi-arrow-right"
            :label="switchLink.label"
          />
          <Button
            severity="secondary"
            text
            icon="pi pi-sign-out"
            :label="t('nav.logout')"
            @click="logout"
          />
        </div>
      </div>

      <p class="profile-hint">{{ t('layout.avatarHint') }}</p>
    </div>

    <template #footer>
      <div class="profile-dialog-actions">
        <Button text severity="secondary" :label="t('common.cancel')" @click="visible = false" />
        <Button
          :label="profileSaving ? t('layout.savingProfile') : t('common.save')"
          :loading="profileSaving"
          @click="saveProfile"
        />
      </div>
    </template>
  </Dialog>
</template>

<style scoped>
  .profile-dialog-body {
    display: grid;
    gap: 1rem;
  }

  .profile-preview {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 1rem;
    border: 1px solid color-mix(in srgb, var(--border) 74%, var(--content-border-strong) 26%);
    border-radius: var(--radius-md);
    background:
      linear-gradient(
        160deg,
        color-mix(in srgb, var(--primary-overlay) 86%, transparent),
        transparent 42%
      ),
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface-card-strong) 96%, transparent),
        transparent 120%
      ),
      color-mix(in srgb, var(--surface-card-strong) 94%, transparent);
    box-shadow:
      inset 0 1px 0 var(--content-glow),
      0 12px 28px color-mix(in srgb, rgb(2 6 23) 10%, transparent);
  }

  .profile-preview-copy {
    display: grid;
    gap: 0.25rem;
  }

  .profile-preview-copy strong {
    font-size: 1rem;
  }

  .profile-preview-copy p,
  .profile-preview-copy small,
  .profile-hint {
    margin: 0;
    color: var(--text-muted);
  }

  .profile-preview-badges {
    display: flex;
    flex-wrap: wrap;
    gap: 0.45rem;
    padding-top: 0.15rem;
  }

  .profile-badge {
    display: inline-flex;
    align-items: center;
    min-height: 1.8rem;
    padding: 0.24rem 0.65rem;
    border-radius: 999px;
    border: 1px solid color-mix(in srgb, var(--border) 76%, var(--primary) 24%);
    background: color-mix(in srgb, var(--surface-card-strong) 92%, var(--primary) 8%);
    color: var(--text);
    font-size: var(--text-xs);
    font-weight: 700;
    letter-spacing: 0.02em;
  }

  .profile-form-grid {
    display: grid;
    gap: 0.9rem;
    padding: 1rem;
    border: 1px solid color-mix(in srgb, var(--border) 74%, var(--content-border-strong) 26%);
    border-radius: var(--radius-md);
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--primary-overlay) 12%, transparent),
        transparent 34%
      ),
      var(--surface-panel);
    box-shadow:
      inset 0 1px 0 var(--content-glow),
      0 12px 26px color-mix(in srgb, rgb(2 6 23) 8%, transparent);
  }

  .profile-identity-row {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0.65rem;
  }

  .identity-block {
    display: grid;
    gap: 0.22rem;
    padding: 0.8rem 0.85rem;
    border-radius: 1rem;
    border: 1px solid color-mix(in srgb, var(--border) 76%, var(--primary) 24%);
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface-card-strong) 94%, transparent),
        transparent 110%
      ),
      color-mix(in srgb, var(--surface-card-strong) 90%, var(--primary) 10%);
    box-shadow:
      inset 0 1px 0 var(--content-glow),
      0 8px 18px color-mix(in srgb, rgb(2 6 23) 7%, transparent);
  }

  .identity-block span {
    color: var(--text-soft);
    font-size: var(--text-xs);
    font-weight: 800;
    letter-spacing: 0.12em;
    text-transform: uppercase;
  }

  .identity-block strong {
    color: var(--text);
    font-size: 0.92rem;
  }

  .profile-preferences {
    display: grid;
    gap: 0.85rem;
    padding: 1rem;
    border: 1px solid color-mix(in srgb, var(--border) 74%, var(--content-border-strong) 26%);
    border-radius: var(--radius-md);
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface-card-strong) 92%, var(--secondary) 8%),
        transparent 36%
      ),
      var(--surface-panel-muted);
    box-shadow:
      inset 0 1px 0 var(--content-glow),
      0 12px 26px color-mix(in srgb, rgb(2 6 23) 8%, transparent);
  }

  .profile-field {
    display: grid;
    gap: 0.4rem;
    color: var(--text);
    font-weight: 700;
  }

  .profile-field span {
    font-size: var(--text-sm);
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }

  .profile-dialog-actions {
    display: flex;
    justify-content: flex-end;
    gap: 0.7rem;
    width: 100%;
  }

  .avatar-frame {
    width: 2.3rem;
    height: 2.3rem;
    border-radius: 999px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(145deg, var(--primary), var(--primary-strong));
    color: var(--primary-contrast);
    font-weight: 800;
    overflow: hidden;
    box-shadow: var(--accent-shadow);
  }

  .avatar-frame.large {
    width: 4.75rem;
    height: 4.75rem;
    font-size: 1.2rem;
  }

  .avatar-frame img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  .preference-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    padding: 0.85rem 0.95rem;
    border-radius: 1rem;
    border: 1px solid color-mix(in srgb, var(--border) 68%, var(--primary) 32%);
    background:
      linear-gradient(
        135deg,
        color-mix(in srgb, var(--primary-overlay) 18%, transparent),
        transparent 44%
      ),
      color-mix(in srgb, var(--surface-card-strong) 90%, var(--primary) 10%);
    box-shadow:
      inset 0 1px 0 var(--content-glow),
      0 8px 18px color-mix(in srgb, rgb(2 6 23) 7%, transparent);
  }

  .preference-row strong {
    display: block;
    margin-bottom: 0.18rem;
    font-size: 0.92rem;
  }

  .preference-row p {
    margin: 0;
    color: var(--text-muted);
    font-size: var(--text-sm);
    max-width: 28rem;
  }

  .profile-secondary-actions {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 0.5rem 0.75rem;
  }

  .profile-link-action {
    text-decoration: none;
  }

  :deep(.profile-dialog .p-inputtext) {
    background: color-mix(in srgb, var(--surface-card-strong) 94%, transparent);
    border: 1px solid color-mix(in srgb, var(--border) 78%, var(--content-border-strong) 22%);
    color: var(--text);
    min-height: 2.9rem;
  }

  :deep(.profile-dialog .p-inputtext::placeholder) {
    color: var(--text-soft);
  }

  :deep(.profile-dialog .p-inputtext:enabled:focus) {
    border-color: color-mix(in srgb, var(--primary) 45%, transparent);
    box-shadow:
      0 0 0 0.18rem color-mix(in srgb, var(--primary) 12%, transparent),
      inset 0 1px 0 var(--content-glow);
  }

  :deep(.profile-dialog .p-selectbutton) {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.45rem;
    width: min(16rem, 100%);
  }

  :deep(.profile-dialog .p-selectbutton .p-togglebutton) {
    min-height: 2.85rem;
    padding-inline: 0.95rem;
  }

  :deep(.profile-dialog .p-selectbutton .p-togglebutton.p-togglebutton-checked) {
    background: linear-gradient(
      135deg,
      color-mix(in srgb, var(--primary) 18%, var(--surface-card-strong)),
      color-mix(in srgb, var(--secondary) 12%, var(--surface-card-strong))
    );
    border-color: color-mix(in srgb, var(--primary) 44%, transparent);
  }

  :deep(.profile-dialog .p-button) {
    min-height: 2.9rem;
  }

  :deep(.profile-dialog .p-button.p-button-text) {
    color: var(--link);
  }

  :deep(.profile-dialog .p-button.p-button-outlined) {
    background: color-mix(in srgb, var(--surface-card-strong) 90%, transparent);
    border-color: color-mix(in srgb, var(--border) 76%, var(--content-border-strong) 24%);
  }

  :deep(.profile-dialog .p-dialog-header),
  :deep(.profile-dialog .p-dialog-content),
  :deep(.profile-dialog .p-dialog-footer) {
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface-card-strong) 96%, transparent),
        transparent 110%
      ),
      var(--surface-strong);
  }

  :deep(.profile-dialog) {
    width: min(34rem, calc(100vw - 2rem));
  }

  :deep(.profile-dialog .p-dialog-header) {
    padding-bottom: 0.85rem;
    border-bottom: 1px solid color-mix(in srgb, var(--border) 72%, transparent);
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--primary-overlay) 78%, transparent),
        transparent 54%
      ),
      color-mix(in srgb, var(--surface-card-strong) 94%, transparent);
  }

  :deep(.profile-dialog .p-dialog-content) {
    padding-top: 0.4rem;
  }

  :deep(.profile-dialog .p-dialog-footer) {
    border-top: 1px solid color-mix(in srgb, var(--border) 72%, transparent);
  }

  @media (max-width: 760px) {
    .profile-preview {
      align-items: flex-start;
      flex-direction: column;
    }

    .profile-identity-row {
      grid-template-columns: 1fr;
    }

    .preference-row,
    .profile-secondary-actions {
      align-items: stretch;
      flex-direction: column;
    }
  }

  @media (max-width: 560px) {
    :deep(.profile-dialog) {
      width: calc(100vw - 1rem);
      margin: 0.5rem;
    }

    .profile-dialog-actions {
      flex-direction: column-reverse;
    }

    .profile-preferences,
    .profile-form-grid,
    .profile-preview {
      padding: 0.95rem;
    }
  }
</style>
