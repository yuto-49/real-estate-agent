import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../utils/api'
import type { AgentPersona, ScenarioVariant, BatchSimulationStatus, BatchSimulationResult, Property } from '../utils/types'
import PersonaBuilder from '../components/PersonaBuilder'
import ScenarioSelector from '../components/ScenarioSelector'
import SimulationRunner from '../components/SimulationRunner'
import ResultsComparison from '../components/ResultsComparison'

const SELECTED_USER_KEY = 'selectedUserId'

interface UserOption {
  id: string
  name: string
  role: string
  budget_max?: number | null
}

export default function SimulationPage() {
  // Step: 'configure' | 'running' | 'results'
  const [step, setStep] = useState<'configure' | 'running' | 'results'>('configure')

  // User/report state
  const [users, setUsers] = useState<UserOption[]>([])
  const [properties, setProperties] = useState<Property[]>([])
  const [reports, setReports] = useState<Array<{ id: string; status: string }>>([])
  const [buyerId, setBuyerId] = useState(() => localStorage.getItem(SELECTED_USER_KEY) || '')
  const [sellerId, setSellerId] = useState('')
  const [reportId, setReportId] = useState('')

  // Config
  const [propertyId, setPropertyId] = useState('')
  const [askingPrice, setAskingPrice] = useState(450000)
  const [initialOffer, setInitialOffer] = useState(400000)
  const [sellerMin, setSellerMin] = useState(420000)
  const [buyerMax, setBuyerMax] = useState(500000)
  const [maxRounds, setMaxRounds] = useState(15)

  // Personas
  const [personas, setPersonas] = useState<{ buyer: AgentPersona | null; seller: AgentPersona | null }>({
    buyer: null, seller: null,
  })

  // Scenarios
  const [availableScenarios, setAvailableScenarios] = useState<ScenarioVariant[]>([])
  const [selectedScenarios, setSelectedScenarios] = useState<Set<string>>(new Set(['balanced_market', 'market_favors_buyer', 'aggressive_buyer']))

  // Batch state
  const [batchStatus, setBatchStatus] = useState<BatchSimulationStatus | null>(null)
  const [batchResult, setBatchResult] = useState<BatchSimulationResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    void loadUsers()
    void loadProperties()
    void loadScenarios()
  }, [])

  useEffect(() => {
    if (buyerId) void loadReports(buyerId)
  }, [buyerId])

  const loadUsers = async () => {
    try {
      const data = await api.users.list()
      setUsers(data.map(u => ({ id: u.id, name: u.name, role: u.role, budget_max: u.budget_max })))
      const buyers = data.filter(u => u.role === 'buyer')
      const sellers = data.filter(u => u.role === 'seller')
      if (!buyerId && buyers.length) setBuyerId(buyers[0].id)
      if (sellers.length) setSellerId(sellers[0].id)
      else if (data.length > 1) setSellerId(data[1].id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load users')
    }
  }

  const loadReports = async (userId: string) => {
    try {
      const data = await api.reports.listByUser(userId)
      setReports(data.filter(r => r.status === 'completed').map(r => ({ id: r.id, status: r.status })))
    } catch {
      // ignore
    }
  }

  const applyPropertyDefaults = (property: Property) => {
    const asking = Number(property.asking_price || 0)
    if (!asking) return
    setAskingPrice(asking)
    setInitialOffer(Math.round(asking * 0.9))
    setSellerMin(Math.round(asking * 0.95))
    setBuyerMax(Math.round(asking * 1.05))
  }

  const loadProperties = async () => {
    try {
      const data = await api.properties.list()
      const items = data.properties as Property[]
      setProperties(items)
      if (!propertyId && items.length > 0) {
        setPropertyId(items[0].id)
        applyPropertyDefaults(items[0])
      }
    } catch {
      setProperties([])
    }
  }

  const loadScenarios = async () => {
    try {
      const data = await api.simulation.getScenarios()
      setAvailableScenarios(data.scenarios)
    } catch {
      // Use defaults
      setAvailableScenarios([
        { name: 'market_favors_buyer', description: 'Low demand, seller urgency', max_rounds: 15, constraints: {} },
        { name: 'market_favors_seller', description: 'Hot market, multiple offers', max_rounds: 12, constraints: {} },
        { name: 'balanced_market', description: 'Normal market conditions', max_rounds: 15, constraints: {} },
        { name: 'aggressive_buyer', description: 'Buyer pushes hard with low offer', max_rounds: 20, constraints: {} },
        { name: 'conservative_approach', description: 'Patient, many rounds', max_rounds: 25, constraints: {} },
        { name: 'time_pressure', description: 'Both sides want quick close', max_rounds: 8, constraints: {} },
      ])
    }
  }

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }, [])

  const pollBatch = useCallback(async (id: string) => {
    try {
      const data = await api.simulation.batchStatus(id) as unknown as BatchSimulationStatus

      if (data.status === 'completed') {
        stopPolling()
        // Don't update batchStatus with result-shaped data — go straight to results
        try {
          const result = await api.simulation.batchResult(id) as unknown as BatchSimulationResult
          setBatchResult(result)
          setStep('results')
        } catch {
          // result endpoint not ready yet — show last known status
          setBatchStatus(data)
        }
        setLoading(false)
      } else {
        setBatchStatus(data)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to poll batch status')
      stopPolling()
      setLoading(false)
    }
  }, [stopPolling])

  const handleToggleScenario = (name: string) => {
    setSelectedScenarios(prev => {
      const next = new Set(prev)
      if (next.has(name)) next.delete(name)
      else next.add(name)
      return next
    })
  }

  const startBatch = async () => {
    if (selectedScenarios.size === 0) {
      setError('Select at least one scenario')
      return
    }
    setError('')
    setLoading(true)
    setBatchStatus(null)
    setBatchResult(null)
    setStep('running')

    try {
      const personaPayload = personas.buyer && personas.seller
        ? { buyer: personas.buyer, seller: personas.seller }
        : undefined

      const data = await api.simulation.batchStart({
        property_id: propertyId,
        asking_price: askingPrice,
        initial_offer: initialOffer,
        seller_minimum: sellerMin,
        buyer_maximum: buyerMax,
        max_rounds: maxRounds,
        buyer_user_id: buyerId,
        seller_user_id: sellerId,
        strategy: 'balanced',
        scenario_names: Array.from(selectedScenarios),
        report_id: reportId || undefined,
        persona_data: personaPayload as Record<string, unknown> | undefined,
      })

      const id = data.batch_id
      pollRef.current = setInterval(() => void pollBatch(id), 2500)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start batch simulation')
      setStep('configure')
      setLoading(false)
    }
  }

  useEffect(() => {
    return () => stopPolling()
  }, [stopPolling])

  const handleReset = () => {
    setBatchStatus(null)
    setBatchResult(null)
    setStep('configure')
    setError('')
  }

  const buyerProfile = users.find(u => u.id === buyerId)

  return (
    <div className="simulation-page">
      <div className="page-title-row">
        <h2>Negotiation Simulation</h2>
        {step !== 'configure' && (
          <button className="secondary-btn" onClick={handleReset}>New Simulation</button>
        )}
      </div>

      {/* Step Indicator */}
      <div className="sim-step-indicator">
        <span className={`sim-step ${step === 'configure' ? 'active' : 'done'}`}>1. Configure</span>
        <span className="sim-step-arrow">&rarr;</span>
        <span className={`sim-step ${step === 'running' ? 'active' : step === 'results' ? 'done' : ''}`}>2. Running</span>
        <span className="sim-step-arrow">&rarr;</span>
        <span className={`sim-step ${step === 'results' ? 'active' : ''}`}>3. Results</span>
      </div>

      {error && <p className="error">{error}</p>}

      {/* STEP 1: Configure */}
      {step === 'configure' && (
        <>
          {/* Persona Builder */}
          <PersonaBuilder
            buyerProfile={buyerProfile ? { name: buyerProfile.name, role: buyerProfile.role, budget_max: buyerProfile.budget_max } : null}
            propertyContext={{ property_id: propertyId, asking_price: askingPrice }}
            personas={personas}
            onPersonasGenerated={(p) => setPersonas(p)}
          />

          {/* Scenario Selector */}
          <ScenarioSelector
            scenarios={availableScenarios}
            selected={selectedScenarios}
            onToggle={handleToggleScenario}
          />

          {/* Simulation Settings */}
          <div className="sim-config">
            <h3>Simulation Settings</h3>
            <div className="sim-config-grid">
              <div className="agent-control-group">
                <label>Buyer</label>
                <select value={buyerId} onChange={e => setBuyerId(e.target.value)}>
                  <option value="">Select buyer</option>
                  {users.map(u => <option key={u.id} value={u.id}>{u.name} ({u.role})</option>)}
                </select>
              </div>
              <div className="agent-control-group">
                <label>Seller</label>
                <select value={sellerId} onChange={e => setSellerId(e.target.value)}>
                  <option value="">Select seller</option>
                  {users.map(u => <option key={u.id} value={u.id}>{u.name} ({u.role})</option>)}
                </select>
              </div>
              <div className="agent-control-group">
                <label>Intelligence Report (optional)</label>
                <select value={reportId} onChange={e => setReportId(e.target.value)}>
                  <option value="">None</option>
                  {reports.map(r => <option key={r.id} value={r.id}>{r.id.slice(0, 12)}...</option>)}
                </select>
              </div>
              <div className="agent-control-group">
                <label>Property (linked to map)</label>
                <select
                  value={propertyId}
                  onChange={e => {
                    const nextId = e.target.value
                    setPropertyId(nextId)
                    const selected = properties.find((p) => p.id === nextId)
                    if (selected) applyPropertyDefaults(selected)
                  }}
                >
                  <option value="">Select property</option>
                  {properties.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.address} - ${Number(p.asking_price || 0).toLocaleString()}
                    </option>
                  ))}
                </select>
              </div>
              <div className="agent-control-group">
                <label>Asking Price ($)</label>
                <input type="number" value={askingPrice} onChange={e => setAskingPrice(Number(e.target.value))} />
              </div>
              <div className="agent-control-group">
                <label>Initial Offer ($)</label>
                <input type="number" value={initialOffer} onChange={e => setInitialOffer(Number(e.target.value))} />
              </div>
              <div className="agent-control-group">
                <label>Seller Minimum ($)</label>
                <input type="number" value={sellerMin} onChange={e => setSellerMin(Number(e.target.value))} />
              </div>
              <div className="agent-control-group">
                <label>Buyer Maximum ($)</label>
                <input type="number" value={buyerMax} onChange={e => setBuyerMax(Number(e.target.value))} />
              </div>
              <div className="agent-control-group">
                <label>Max Rounds ({maxRounds})</label>
                <input
                  type="range"
                  min={5}
                  max={30}
                  value={maxRounds}
                  onChange={e => setMaxRounds(Number(e.target.value))}
                  style={{ width: '100%' }}
                />
              </div>
            </div>
            {properties.length === 0 && (
              <p className="error" style={{ marginTop: '0.75rem' }}>
                No active properties found. Add or seed properties to link simulation results to the map.
              </p>
            )}
            <button
              className="primary-btn sim-start-btn"
              onClick={() => void startBatch()}
              disabled={!propertyId || !buyerId || !sellerId || selectedScenarios.size === 0 || loading}
            >
              Start Batch Simulation ({selectedScenarios.size} scenarios)
            </button>
          </div>
        </>
      )}

      {/* STEP 2: Running */}
      {step === 'running' && batchStatus && (
        <SimulationRunner batchStatus={batchStatus} />
      )}
      {step === 'running' && !batchStatus && (
        <div className="sim-thinking">
          <span className="workflow-spinner" /> Starting simulation...
        </div>
      )}

      {/* STEP 3: Results */}
      {step === 'results' && batchResult && (
        <ResultsComparison
          result={batchResult}
          propertyId={propertyId}
          askingPrice={askingPrice}
        />
      )}
    </div>
  )
}
