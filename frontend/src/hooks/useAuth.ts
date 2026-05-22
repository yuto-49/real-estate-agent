import { useEffect, useState } from 'react'
import type { Session, User } from '@supabase/supabase-js'

import { supabase } from '../utils/supabase'

interface AuthState {
  session: Session | null
  user: User | null
  loading: boolean
}

export function useAuth(): AuthState & {
  signIn: (email: string, password: string) => Promise<void>
  signUp: (email: string, password: string) => Promise<void>
  signOut: () => Promise<void>
} {
  const [state, setState] = useState<AuthState>({
    session: null,
    user: null,
    loading: true,
  })

  useEffect(() => {
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
      const { error } = await supabase.auth.signInWithPassword({ email, password })
      if (error) throw error
    },
    signUp: async (email, password) => {
      const { error } = await supabase.auth.signUp({ email, password })
      if (error) throw error
    },
    signOut: async () => {
      const { error } = await supabase.auth.signOut()
      if (error) throw error
    },
  }
}
