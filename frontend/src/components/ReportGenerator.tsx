import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../utils/api'
import type { UserProfile } from '../utils/types'

const DEFAULT_QUESTION = 'What is the best investment strategy for this buyer?'

interface Props {
  users: UserProfile[]
  selectedUserId: string
  onUserChange: (userId: string) => void
}

export default function ReportGenerator({ users, selectedUserId, onUserChange }: Props) {
  const navigate = useNavigate()
  const [question, setQuestion] = useState(DEFAULT_QUESTION)
  const [isGenerating, setIsGenerating] = useState(false)
  const [error, setError] = useState('')
  const [generatedReportId, setGeneratedReportId] = useState('')

  const handleGenerate = async () => {
    if (!selectedUserId) return
    setIsGenerating(true)
    setError('')
    setGeneratedReportId('')
    try {
      const data = await api.reports.generate({
        user_id: selectedUserId,
        question,
      })
      setGeneratedReportId(data.id)
      navigate(`/analysis/${data.id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate report')
    } finally {
      setIsGenerating(false)
    }
  }

  return (
    <div className="report-generator">
      <h4>Generate Intelligence Report</h4>
      <div className="agent-control-group" style={{ marginBottom: '0.5rem' }}>
        <label>Investor Profile</label>
        <select value={selectedUserId} onChange={(e) => onUserChange(e.target.value)}>
          <option value="">Select a user</option>
          {users.map((u) => (
            <option key={u.id} value={u.id}>{u.name} ({u.role})</option>
          ))}
        </select>
      </div>
      <textarea
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        rows={3}
        placeholder="Report question"
      />
      <button onClick={() => void handleGenerate()} disabled={isGenerating || !selectedUserId}>
        {isGenerating ? 'Generating...' : 'Generate Report'}
      </button>
      {error && <p className="error">{error}</p>}
      {generatedReportId && (
        <p>Report queued — redirecting...</p>
      )}
    </div>
  )
}
