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
  const [popupOpen, setPopupOpen] = useState(!!simIdParam || !!batchIdParam)

  const handleSimulationSelect = useCallback((simId: string, batchId?: string) => {
    setActiveSimId(simId)
    setActiveBatchId(batchId || null)
    setPopupOpen(true)
  }, [])

  const handleVisualizationLoaded = useCallback((viz: PropertyVisualization) => {
    setVisualization(viz)
    // Auto-open popup if we have a simulation ID from URL or from the property
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
      <div style={{ padding: '40px', textAlign: 'center' }}>
        <h2>No property selected</h2>
        <button
          onClick={() => navigate('/simulation')}
          style={{ marginTop: '12px', padding: '8px 16px', cursor: 'pointer' }}
        >
          Go to Simulation
        </button>
      </div>
    )
  }

  return (
    <div style={{ width: '100vw', height: 'calc(100vh - 56px)', position: 'relative' }}>
      {/* Full-screen map */}
      <PropertySimulationMap
        propertyId={propertyId}
        onSimulationSelect={handleSimulationSelect}
        onVisualizationLoaded={handleVisualizationLoaded}
      />

      {/* Back button */}
      <button
        onClick={() => navigate('/simulation')}
        style={{
          position: 'absolute',
          top: '12px',
          left: '60px',
          padding: '8px 14px',
          fontSize: '13px',
          backgroundColor: '#fff',
          border: '1px solid #e2e8f0',
          borderRadius: '6px',
          cursor: 'pointer',
          boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
          zIndex: 10,
        }}
      >
        Back to Simulation
      </button>

      {/* Simulation Popup */}
      {popupOpen && activeSimId && (
        <SimulationPopup
          simulationId={activeSimId}
          batchId={activeBatchId || undefined}
          propertyVisualization={visualization}
          onClose={handleClosePopup}
        />
      )}
    </div>
  )
}
