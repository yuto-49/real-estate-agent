import { useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'

import { useAuth } from '../hooks/useAuth'

type Mode = 'signin' | 'signup'

const DEV_EMAIL = 'dev@realestate.local'
const DEV_PASSWORD = 'DevPassword123!'

export default function SignInPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { signIn, signUp } = useAuth()
  const [mode, setMode] = useState<Mode>('signin')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const fromPath = (location.state as { from?: string } | null)?.from ?? '/'

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      if (mode === 'signin') {
        await signIn(email, password)
      } else {
        await signUp(email, password)
      }
      navigate(fromPath, { replace: true })
    } catch (err) {
      const message = err instanceof Error ? err.message : '認証に失敗しました。'
      setError(message)
    } finally {
      setSubmitting(false)
    }
  }

  function fillDevCredentials() {
    setEmail(DEV_EMAIL)
    setPassword(DEV_PASSWORD)
  }

  return (
    <div style={{ maxWidth: 380, margin: '4rem auto', padding: '0 1rem' }}>
      <h2 style={{ marginBottom: '1rem' }}>
        {mode === 'signin' ? 'ログイン' : 'アカウント作成'}
      </h2>

      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
        <label style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
          <span style={{ fontSize: '0.85rem', opacity: 0.8 }}>メールアドレス</span>
          <input
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
            autoComplete="email"
            style={inputStyle}
          />
        </label>
        <label style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
          <span style={{ fontSize: '0.85rem', opacity: 0.8 }}>パスワード</span>
          <input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
            minLength={8}
            autoComplete={mode === 'signin' ? 'current-password' : 'new-password'}
            style={inputStyle}
          />
        </label>

        {error && (
          <div role="alert" style={{ color: '#c0392b', fontSize: '0.85rem' }}>
            {error}
          </div>
        )}

        <button type="submit" disabled={submitting} style={primaryButton}>
          {submitting ? '処理中…' : mode === 'signin' ? 'ログイン' : '登録する'}
        </button>
      </form>

      <div style={{ marginTop: '1rem', fontSize: '0.85rem', display: 'flex', justifyContent: 'space-between' }}>
        <button
          type="button"
          onClick={() => setMode((m) => (m === 'signin' ? 'signup' : 'signin'))}
          style={linkButton}
        >
          {mode === 'signin' ? 'アカウントを作成する' : 'すでにアカウントをお持ちの方'}
        </button>
        <Link to="/" style={{ textDecoration: 'none' }}>
          戻る
        </Link>
      </div>

      <hr style={{ margin: '1.5rem 0', opacity: 0.3 }} />

      <div style={{ fontSize: '0.8rem', opacity: 0.75 }}>
        <strong>開発用ショートカット</strong> — 作成元:{' '}
        <code>scripts/create_dev_user.py</code>:
        <pre style={devBlock}>
          {`email:    ${DEV_EMAIL}\npassword: ${DEV_PASSWORD}`}
        </pre>
        <button type="button" onClick={fillDevCredentials} style={ghostButton}>
          開発用資格情報を入力
        </button>
      </div>
    </div>
  )
}

const inputStyle: React.CSSProperties = {
  padding: '0.55rem 0.75rem',
  borderRadius: 6,
  border: '1px solid #d0d4dc',
  fontSize: '1rem',
}

const primaryButton: React.CSSProperties = {
  padding: '0.6rem 0.75rem',
  borderRadius: 6,
  border: 'none',
  background: '#2c5282',
  color: 'white',
  fontWeight: 600,
  cursor: 'pointer',
}

const linkButton: React.CSSProperties = {
  background: 'none',
  border: 'none',
  color: '#2c5282',
  cursor: 'pointer',
  padding: 0,
  fontSize: '0.85rem',
}

const ghostButton: React.CSSProperties = {
  marginTop: '0.5rem',
  background: 'transparent',
  border: '1px solid #2c5282',
  color: '#2c5282',
  borderRadius: 4,
  padding: '0.3rem 0.6rem',
  fontSize: '0.8rem',
  cursor: 'pointer',
}

const devBlock: React.CSSProperties = {
  background: '#f4f6f8',
  padding: '0.5rem',
  borderRadius: 4,
  marginTop: '0.4rem',
  fontSize: '0.75rem',
  whiteSpace: 'pre',
}
