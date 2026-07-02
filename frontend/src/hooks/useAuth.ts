import { useEffect, useState } from 'react'
import type { Session, User } from '@supabase/supabase-js'

import { supabase } from '../utils/supabase'

interface AuthState {
  session: Session | null
  user: User | null
  loading: boolean
}

/** Fake session/user returned when Supabase is not configured (dev mode). */
const DEV_USER = {
  id: 'dev-local-user',
  email: 'dev@realestate.local',
  aud: 'authenticated',
  role: 'authenticated',
  app_metadata: {},
  user_metadata: {},
  created_at: '',
} as unknown as User

const DEV_SESSION = { user: DEV_USER, access_token: 'dev-token' } as unknown as Session

export function useAuth(): AuthState & {
  signIn: (email: string, password: string) => Promise<void>
  signUp: (email: string, password: string) => Promise<void>
  signOut: () => Promise<void>
} {
  const devMode = import.meta.env.DEV

  const [state, setState] = useState<AuthState>({
    session: devMode ? DEV_SESSION : null,
    user: devMode ? DEV_USER : null,
    loading: devMode ? false : true,
  })

  useEffect(() => {
    if (devMode) return

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
  }, [devMode])

  return {
    ...state,
    signIn: async (email, password) => {
      if (devMode) {
        setState({ session: DEV_SESSION, user: DEV_USER, loading: false })
        return
      }
      const { error } = await supabase.auth.signInWithPassword({ email, password })
      if (error) throw error
    },
    signUp: async (email, password) => {
      if (devMode) {
        setState({ session: DEV_SESSION, user: DEV_USER, loading: false })
        return
      }
      const { error } = await supabase.auth.signUp({ email, password })
      if (error) throw error
    },
    signOut: async () => {
      if (devMode) {
        setState({ session: null, user: null, loading: false })
        return
      }
      const { error } = await supabase.auth.signOut()
      if (error) throw error
    },
  }
}
