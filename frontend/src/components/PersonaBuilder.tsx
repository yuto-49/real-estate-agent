import { useState } from 'react'
import { api } from '../utils/api'
import type { AgentPersona } from '../utils/types'

interface Props {
  buyerProfile: Record<string, unknown> | null
  propertyContext: Record<string, unknown> | null
  personas: { buyer: AgentPersona | null; seller: AgentPersona | null }
  onPersonasGenerated: (personas: { buyer: AgentPersona; seller: AgentPersona }) => void
}

function PersonaCard({ persona }: { persona: AgentPersona }) {
  return (
    <div className="persona-card">
      <div className="persona-card-header">
        <span className={`persona-role ${persona.role}`}>{persona.role.toUpperCase()}</span>
        <span className="persona-name">{persona.name}</span>
      </div>
      <div className="persona-traits">
        <div className="persona-trait">
          <span className="persona-trait-label">MBTI</span>
          <span className="persona-trait-value">{persona.personality_type}</span>
        </div>
        <div className="persona-trait">
          <span className="persona-trait-label">Style</span>
          <span className="persona-trait-value">{persona.negotiation_style}</span>
        </div>
        <div className="persona-trait">
          <span className="persona-trait-label">Risk</span>
          <span className="persona-trait-value">{persona.risk_tolerance}</span>
        </div>
        <div className="persona-trait">
          <span className="persona-trait-label">Experience</span>
          <span className="persona-trait-value">{persona.experience_level}</span>
        </div>
      </div>
      <p className="persona-background">{persona.background}</p>
      <div className="persona-lists">
        <div>
          <span className="persona-list-label">Motivations</span>
          <ul>{persona.motivations.map((m, i) => <li key={i}>{m}</li>)}</ul>
        </div>
        <div>
          <span className="persona-list-label">Pressure Points</span>
          <ul>{persona.pressure_points.map((p, i) => <li key={i}>{p}</li>)}</ul>
        </div>
        <div>
          <span className="persona-list-label">Strengths</span>
          <ul>{persona.strengths.map((s, i) => <li key={i}>{s}</li>)}</ul>
        </div>
      </div>
    </div>
  )
}

export default function PersonaBuilder({ buyerProfile, propertyContext, personas, onPersonasGenerated }: Props) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleGenerate = async () => {
    setLoading(true)
    setError('')
    try {
      const result = await api.simulation.generatePersonas({
        buyer_profile: buyerProfile || {},
        property_context: propertyContext || {},
      })
      onPersonasGenerated({
        buyer: result.buyer as unknown as AgentPersona,
        seller: result.seller as unknown as AgentPersona,
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate personas')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="persona-builder">
      <div className="persona-builder-header">
        <h4>Agent Personas</h4>
        <button
          className="secondary-btn"
          onClick={() => void handleGenerate()}
          disabled={loading}
        >
          {loading ? 'Generating...' : personas.buyer ? 'Regenerate' : 'Generate Personas'}
        </button>
      </div>
      {error && <p className="error">{error}</p>}
      {personas.buyer && personas.seller && (
        <div className="persona-cards-row">
          <PersonaCard persona={personas.buyer} />
          <PersonaCard persona={personas.seller} />
        </div>
      )}
      {!personas.buyer && !loading && (
        <p style={{ color: '#888', fontSize: '0.85rem' }}>
          Click "Generate Personas" to create buyer and seller profiles for the simulation.
        </p>
      )}
    </div>
  )
}
