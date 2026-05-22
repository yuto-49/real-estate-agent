import { FormEvent, useState } from 'react'
import { isSupabaseConfigured, supabase } from '../auth/supabase'

type AuthMode = 'signin' | 'signup'

export default function AuthPage() {
  const [mode, setMode] = useState<AuthMode>('signin')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    setMessage('')
    setLoading(true)
    try {
      if (mode === 'signin') {
        const { error: signInError } = await supabase.auth.signInWithPassword({
          email: email.trim(),
          password,
        })
        if (signInError) throw signInError
        setMessage('Signed in successfully.')
      } else {
        const { error: signUpError } = await supabase.auth.signUp({
          email: email.trim(),
          password,
        })
        if (signUpError) throw signUpError
        setMessage('Account created. You can now sign in.')
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Authentication failed')
    } finally {
      setLoading(false)
    }
  }

  if (!isSupabaseConfigured) {
    return (
      <div className="analysis-page">
        <h2>Authentication Setup Required</h2>
        <p className="error">
          Public runtime config is missing the Supabase URL or publishable key. Set them in the backend environment so{' '}
          <code>/api/config/public</code>{' '}
          can provide them to the frontend.
        </p>
      </div>
    )
  }

  return (
    <div className="analysis-page" style={{ maxWidth: 560, margin: '2rem auto' }}>
      <h2>{mode === 'signin' ? 'Sign In' : 'Create Account'}</h2>
      <form onSubmit={handleSubmit} className="user-form">
        <div className="form-section">
          <div className="form-group">
            <label>Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
            />
          </div>
          <div className="form-group">
            <label>Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={6}
              autoComplete={mode === 'signin' ? 'current-password' : 'new-password'}
            />
          </div>
        </div>

        {error && <p className="error">{error}</p>}
        {message && <p style={{ color: '#22c55e' }}>{message}</p>}

        <div className="form-actions">
          <button className="primary-btn" type="submit" disabled={loading}>
            {loading ? 'Please wait...' : mode === 'signin' ? 'Sign In' : 'Sign Up'}
          </button>
          <button
            className="secondary-btn"
            type="button"
            onClick={() => setMode((prev) => (prev === 'signin' ? 'signup' : 'signin'))}
            disabled={loading}
          >
            {mode === 'signin' ? 'Create account' : 'Back to sign in'}
          </button>
        </div>
      </form>
    </div>
  )
}
