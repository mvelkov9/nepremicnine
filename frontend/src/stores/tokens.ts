// Module-level reactive refs backed by localStorage.
// Kept separate from auth.js to avoid a circular dependency with useApi.js:
//   auth.js → useApi.js → tokens.js (no cycle)
import { useLocalStorage } from '@vueuse/core'

export const accessToken = useLocalStorage<string | null>('access_token', null)
export const refreshToken = useLocalStorage<string | null>('refresh_token', null)
