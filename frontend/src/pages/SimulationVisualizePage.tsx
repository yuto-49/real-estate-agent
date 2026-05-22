import { useState, useCallback } from 'react'
import { useParams, useSearchParams, useNavigate } from 'react-router-dom'
import PropertySimulationMap from '../components/PropertySimulationMap'
import SimulationPopup from '../components/SimulationPopup'
import type { PropertyVisualization } from '../utils/types'

export default function SimulationVisualizePage() {
  const { propertyId } = useParams<{ propertyId: string }>()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()

  const simIdParam = searchParams.get('sim')
  const batchIdParam = searchParams.get('batch')

  const [activeSimId, setActiveSimId] = useState<string | null>(simIdParam)
  const [activeBatchId, setActiveBatchId] = useState<string | null>(batchIdParam)
  const [visualization, setVisualization] = useState<PropertyVisualization | null>(null)
  const [popupOpen, setPopupOpen] = useState(Boolean(simIdParam || batchIdParam))

  const handleSimulationSelect = useCallback((simId: string, batchId?: string) => {
    setActiveSimId(simId)
    setActiveBatchId(batchId || null)
    setPopupOpen(true)
  }, [])

  const handleVisualizationLoaded = useCallback((viz: PropertyVisualization) => {
    setVisualization(viz)
    if (!popupOpen && !simIdParam && viz.simulation_ids.length > 0) {
      setActiveSimId(viz.simulation_ids[0])
      setPopupOpen(true)
    }
  }, [popupOpen, simIdParam])

  const handleClosePopup = useCallback(() => {
    setPopupOpen(false)
  }, [])

  if (!propertyId) {
    return (
      <div className="simulation-replay-empty">
        <div className="simulation-replay-empty-card">
          <h2>No property selected</h2>
          <p>Choose a property from simulation results to load the replay map.</p>
          <button
            type="button"
            className="primary-btn"
            onClick={() => navigate('/simulation')}
          >
            Go to Simulation
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="simulation-replay-page">
      <div className="simulation-replay-stage">
        <PropertySimulationMap
          propertyId={propertyId}
          onSimulationSelect={handleSimulationSelect}
          onVisualizationLoaded={handleVisualizationLoaded}
        />

        <button
          type="button"
          className="simulation-replay-back secondary-btn"
          onClick={() => navigate('/simulation')}
        >
          Back to Simulation
        </button>

        {popupOpen && activeSimId && (
          <SimulationPopup
            simulationId={activeSimId}
            batchId={activeBatchId || undefined}
            propertyVisualization={visualization}
            onClose={handleClosePopup}
          />
        )}
      </div>
    </div>
  )
}
