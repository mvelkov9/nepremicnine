<script setup lang="ts">
  import { computed, ref, watch } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { useAuthStore } from '../../stores/auth'
  import { useToast } from '../../composables/useToast'
  import { getApiErrorMessage } from '../../utils/apiError'

  const visible = defineModel<boolean>('visible', { default: false })

  const { t } = useI18n()
  const auth = useAuthStore()
  const { showToast } = useToast()

  const profileSaving = ref(false)
  const profileForm = ref({
    full_name: '',
    avatar_url: '',
  })

  const avatarUrl = computed(() => auth.user?.avatar_url || '')
  const profileAvatarUrl = computed(() => profileForm.value.avatar_url.trim() || avatarUrl.value)

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
          <p>{{ auth.user?.email }}</p>
          <small>{{ t('layout.profileDescription') }}</small>
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

      <p class="profile-hint">{{ t('layout.avatarHint') }}</p>
    </div>

    <template #footer>
      <div class="profile-dialog-actions">
        <Button
          text
          severity="secondary"
          :label="t('common.cancel')"
          @click="visible = false"
        />
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
  }

  .profile-preview-copy {
    display: grid;
    gap: 0.2rem;
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

  .profile-form-grid {
    display: grid;
    gap: 0.9rem;
  }

  .profile-field {
    display: grid;
    gap: 0.4rem;
    color: var(--text);
    font-weight: 700;
  }

  .profile-field span {
    font-size: 0.83rem;
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
    background: linear-gradient(145deg, var(--shell-brand-start), var(--shell-brand-end));
    color: var(--shell-brand-contrast);
    font-weight: 800;
    overflow: hidden;
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

  :deep(.profile-dialog) {
    width: min(34rem, calc(100vw - 2rem));
  }

  :deep(.profile-dialog .p-dialog-header) {
    padding-bottom: 0.85rem;
  }

  :deep(.profile-dialog .p-dialog-content) {
    padding-top: 0.4rem;
  }

  @media (max-width: 760px) {
    .profile-preview {
      align-items: flex-start;
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
  }
</style>
