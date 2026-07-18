import { useEffect, useState } from 'react'
import type { Session, User } from '@supabase/supabase-js'

import { supabase } from '../utils/supabase'

interface AuthState {
  session: Session | null
  user: User | null
  loading: boolean
}

// Local dev escape hatch. When VITE_DEV_BYPASS_AUTH=true, the app renders as a
// synthetic signed-in user without ever calling Supabase — useful when the
// Supabase project is paused/unconfigured and you only want to exercise the
// (un-authed) backend, e.g. the strategy simulation. Off by default, so a
// missing/false flag leaves the real Supabase flow completely untouched.
const DEV_BYPASS_AUTH = import.meta.env.VITE_DEV_BYPASS_AUTH === 'true'

const DEV_USER = {
  id: 'dev-user-0001',
  email: 'dev@realestate.local',
  aud: 'authenticated',
  role: 'authenticated',
  app_metadata: {},
  user_metadata: {},
  created_at: new Date(0).toISOString(),
} as unknown as User

const DEV_SESSION = {
  access_token: 'dev-bypass',
  refresh_token: 'dev-bypass',
  expires_in: 3600,
  token_type: 'bearer',
  user: DEV_USER,
} as unknown as Session

export function useAuth(): AuthState & {
  signIn: (email: string, password: string) => Promise<void>
  signUp: (email: string, password: string) => Promise<void>
  signOut: () => Promise<void>
} {
  const [state, setState] = useState<AuthState>(
    DEV_BYPASS_AUTH
      ? { session: DEV_SESSION, user: DEV_USER, loading: false }
      : { session: null, user: null, loading: true },
  )

  useEffect(() => {
    if (DEV_BYPASS_AUTH) return // synthetic session — never touch Supabase
    let active = true
    supabase.auth.getSession().then(({ data }) => {
      if (!active) return
      setState({ session: data.session, user: data.session?.user ?? null, loading: false })
    })

    const { data: subscription } = supabase.auth.onAuthStateChange((_event, session) => {
      setState({ session, user: session?.user ?? null, loading: false })
    })

    return () => {
      active = false
      subscription.subscription.unsubscribe()
    }
  }, [])

  return {
    ...state,
    signIn: async (email, password) => {
      if (DEV_BYPASS_AUTH) return // already "signed in" as the dev user
      const { error } = await supabase.auth.signInWithPassword({ email, password })
      if (error) throw error
    },
    signUp: async (email, password) => {
      if (DEV_BYPASS_AUTH) return
      const { error } = await supabase.auth.signUp({ email, password })
      if (error) throw error
    },
    signOut: async () => {
      if (DEV_BYPASS_AUTH) return
      const { error } = await supabase.auth.signOut()
      if (error) throw error
    },
  }
}
