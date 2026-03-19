// Module-level reactive refs backed by localStorage.
// Kept separate from auth.ts to avoid a circular dependency with useApi.ts:
//   auth.ts → useApi.ts → tokens.ts (no cycle)
import { useLocalStorage } from '@vueuse/core'

export const accessToken = useLocalStorage<string | null>('access_token', null)
export const refreshToken = useLocalStorage<string | null>('refresh_token', null)
