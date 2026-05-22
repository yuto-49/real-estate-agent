import { useState } from 'react'
import { api } from '../utils/api'
import type { AgentPersona } from '../utils/types'
import SimulationPersonaCard from './SimulationPersonaCard'

interface Props {
  buyerProfile: Record<string, unknown> | null
  propertyContext: Record<string, unknown> | null
  personas: { buyer: AgentPersona | null; seller: AgentPersona | null }
  onPersonasGenerated: (personas: { buyer: AgentPersona; seller: AgentPersona }) => void
}

function PersonaCard({ persona }: { persona: AgentPersona }) {
  return (
    <SimulationPersonaCard
      badge={persona.role.toUpperCase()}
      badgeTone={persona.role === 'buyer' ? 'buyer' : 'seller'}
      name={persona.name}
      subtitle={`${persona.personality_type} • ${persona.negotiation_style}`}
      traits={[
        { label: 'MBTI', value: persona.personality_type },
        { label: 'Style', value: persona.negotiation_style },
        { label: 'Risk', value: persona.risk_tolerance },
        { label: 'Experience', value: persona.experience_level },
      ]}
      summary={<p>{persona.background}</p>}
      lists={[
        { label: 'Motivations', items: persona.motivations },
        { label: 'Pressure Points', items: persona.pressure_points },
        { label: 'Strengths', items: persona.strengths },
      ]}
    />
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
          type="button"
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
        <p className="persona-builder-copy">
          Click "Generate Personas" to create buyer and seller profiles for the simulation.
        </p>
      )}
    </div>
  )
}
