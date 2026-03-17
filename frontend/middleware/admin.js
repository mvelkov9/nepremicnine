import { useAuthStore } from '~/legacy/stores/auth'

export default defineNuxtRouteMiddleware(async (to) => {
  const auth = useAuthStore()
  const user = await auth.init()

  if (!user) {
    return navigateTo(`/login?redirect=${encodeURIComponent(to.fullPath)}`)
  }

  if (!auth.isAdmin) {
    return navigateTo('/')
  }
})
