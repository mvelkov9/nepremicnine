import { useAuthStore } from '~/legacy/stores/auth'

export default defineNuxtRouteMiddleware(async () => {
  const auth = useAuthStore()
  const user = await auth.init()

  if (user) {
    return navigateTo('/')
  }
})
