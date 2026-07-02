/**
 * Re-exports the singleton Supabase client from the runtime-config module.
 *
 * All auth and API code should import from here — the underlying client is
 * created lazily after loadRuntimeConfig() resolves in main.tsx, so it uses
 * server-provided credentials (no VITE_* build-time vars required).
 */
export { getAccessToken, isSupabaseConfigured } from '../config/runtime'
import { getSupabaseClient } from '../config/runtime'

/** Convenience re-export so existing `import { supabase }` sites keep working. */
export const supabase = new Proxy({} as ReturnType<typeof getSupabaseClient>, {
  get(_target, prop, receiver) {
    return Reflect.get(getSupabaseClient(), prop, receiver)
  },
})
