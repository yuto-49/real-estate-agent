import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../utils/api'
import type { UserProfile } from '../utils/types'

interface Props {
  users: UserProfile[]
  selectedUserId: string
  onUserChange: (userId: string) => void
}

const CONSTRUCTION_TYPES = ['RC', 'SRC', '鉄骨', '軽量鉄骨', '木造']

export default function ReportGenerator({ users, selectedUserId, onUserChange }: Props) {
  const navigate = useNavigate()
  const [cityCode, setCityCode] = useState('')
  const [zipCode, setZipCode] = useState('')
  const [address, setAddress] = useState('')
  const [menseki, setMenseki] = useState('')
  const [builtYear, setBuiltYear] = useState('')
  const [constructionType, setConstructionType] = useState('RC')
  const [walkMinutes, setWalkMinutes] = useState('')
  const [isComputing, setIsComputing] = useState(false)
  const [error, setError] = useState('')

  const handleCompute = async () => {
    if (!cityCode && !zipCode) {
      setError('市区町村コードまたは郵便番号を入力してください')
      return
    }
    setIsComputing(true)
    setError('')
    try {
      const sateiResult = await api.satei.compute({
        city_code: cityCode || undefined,
        zip_code: zipCode || undefined,
        address: address || undefined,
        menseki_m2: menseki ? parseFloat(menseki) : undefined,
        built_year: builtYear ? parseInt(builtYear) : undefined,
        construction_type: constructionType,
        walk_minutes: walkMinutes ? parseInt(walkMinutes) : undefined,
        user_id: selectedUserId || undefined,
      })

      if (sateiResult.session_id) {
        navigate(`/analysis/${sateiResult.session_id}`)
      } else if (sateiResult.comp_count === 0) {
        setError('該当エリアの取引事例が見つかりませんでした。条件を変更してください。')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '査定の計算に失敗しました')
    } finally {
      setIsComputing(false)
    }
  }

  return (
    <div className="report-generator">
      <h4>査定コンプグリッド (Satei Comp Grid)</h4>

      <div className="agent-control-group" style={{ marginBottom: '0.5rem' }}>
        <label>ユーザー</label>
        <select value={selectedUserId} onChange={(e) => onUserChange(e.target.value)}>
          <option value="">選択してください</option>
          {users.map((u) => (
            <option key={u.id} value={u.id}>{u.name} ({u.role})</option>
          ))}
        </select>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem', marginBottom: '0.5rem' }}>
        <div className="agent-control-group">
          <label>市区町村コード</label>
          <input type="text" value={cityCode} onChange={(e) => setCityCode(e.target.value)} placeholder="例: 13119" />
        </div>
        <div className="agent-control-group">
          <label>郵便番号</label>
          <input type="text" value={zipCode} onChange={(e) => setZipCode(e.target.value)} placeholder="例: 1730004" />
        </div>
      </div>

      <div className="agent-control-group" style={{ marginBottom: '0.5rem' }}>
        <label>住所 (任意)</label>
        <input type="text" value={address} onChange={(e) => setAddress(e.target.value)} placeholder="例: 板橋区板橋1-42-5" />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0.5rem', marginBottom: '0.5rem' }}>
        <div className="agent-control-group">
          <label>専有面積 (m²)</label>
          <input type="number" value={menseki} onChange={(e) => setMenseki(e.target.value)} placeholder="25" />
        </div>
        <div className="agent-control-group">
          <label>築年</label>
          <input type="number" value={builtYear} onChange={(e) => setBuiltYear(e.target.value)} placeholder="2010" />
        </div>
        <div className="agent-control-group">
          <label>駅徒歩 (分)</label>
          <input type="number" value={walkMinutes} onChange={(e) => setWalkMinutes(e.target.value)} placeholder="5" />
        </div>
      </div>

      <div className="agent-control-group" style={{ marginBottom: '0.75rem' }}>
        <label>構造</label>
        <select value={constructionType} onChange={(e) => setConstructionType(e.target.value)}>
          {CONSTRUCTION_TYPES.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
      </div>

      <button onClick={() => void handleCompute()} disabled={isComputing || (!cityCode && !zipCode)}>
        {isComputing ? '計算中...' : '査定を実行'}
      </button>
      {error && <p className="error">{error}</p>}
    </div>
  )
}
