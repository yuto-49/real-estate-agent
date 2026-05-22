import { createClient, type SupabaseClient } from '@supabase/supabase-js'

const url = import.meta.env.VITE_SUPABASE_URL
const publishableKey = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY

export const isSupabaseConfigured = Boolean(url && publishableKey)

if (!isSupabaseConfigured) {
  // Loud warning so you see it in DevTools instead of a blank page.
  // eslint-disable-next-line no-console
  console.warn(
    '[supabase] VITE_SUPABASE_URL or VITE_SUPABASE_PUBLISHABLE_KEY missing. ' +
      'Auth flows will fail until both are set in the project root .env. ' +
      'Vite is configured with envDir=".." so values come from the parent directory.',
  )
}

// createClient throws on empty string — fall back to harmless placeholders so
// the module still loads and the rest of the app can render. Auth calls will
// fail with a clear runtime error rather than a white screen.
export const supabase: SupabaseClient = createClient(
  url || 'http://localhost:0',
  publishableKey || 'missing-publishable-key',
  {
    auth: {
      persistSession: isSupabaseConfigured,
      autoRefreshToken: isSupabaseConfigured,
      detectSessionInUrl: isSupabaseConfigured,
      storageKey: 'real-estate-agent.session',
    },
  },
)

export async function getAccessToken(): Promise<string | null> {
  if (!isSupabaseConfigured) return null
  const { data } = await supabase.auth.getSession()
  return data.session?.access_token ?? null
}
