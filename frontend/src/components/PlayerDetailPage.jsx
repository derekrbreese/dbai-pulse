import { useState, useEffect } from 'react'
import { apiFetch } from '../api/client'
import useAsyncRequest from '../hooks/useAsyncRequest'
import EnhancedCard from './EnhancedCard'
import PerformanceChart from './PerformanceChart'
import { PlayerCardSkeleton, ChartSkeleton } from './SkeletonLoader'

function PlayerDetailPage({ playerId }) {
  const { execute, loading, error } = useAsyncRequest()
  const [data, setData] = useState(null)

  useEffect(() => {
    if (!playerId) return
    execute(async () => {
      const response = await apiFetch(`/api/players/${playerId}`)
      if (!response.ok) throw new Error('Failed to fetch player data')
      const result = await response.json()
      setData(result)
      return result
    }).catch(() => {})
  }, [playerId, execute])

  return (
    <div className="player-detail-page">
      <button className="back-button" onClick={() => window.history.back()}>
        Back
      </button>

      {(loading || (!data && !error)) && (
        <div className="player-section">
          <PlayerCardSkeleton />
          <ChartSkeleton />
        </div>
      )}

      {error && (
        <div className="error-state">
          <p>{error}</p>
        </div>
      )}

      {data && !loading && (
        <section className="player-section">
          <EnhancedCard data={data} />
          <PerformanceChart
            playerId={playerId}
            playerName={data.player?.name}
          />
        </section>
      )}
    </div>
  )
}

export default PlayerDetailPage
