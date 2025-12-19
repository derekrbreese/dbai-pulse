import { useState } from 'react'
import { createPortal } from 'react-dom'
import './PulseButton.css'
import PulseModal from './PulseModal'

function PulseButton({ sleeperId, playerName }) {
    const [loading, setLoading] = useState(false)
    const [pulseData, setPulseData] = useState(null)
    const [error, setError] = useState(null)
    const [showModal, setShowModal] = useState(false)

    const fetchPulse = async () => {
        if (!sleeperId) return

        setLoading(true)
        setError(null)

        try {
            const response = await fetch(`http://localhost:8000/api/players/${sleeperId}/pulse`)
            if (!response.ok) {
                throw new Error('Failed to fetch Pulse analysis')
            }

            const data = await response.json()
            setPulseData(data)
            setShowModal(true)
        } catch (err) {
            setError(err.message)
        } finally {
            setLoading(false)
        }
    }

    return (
        <>
            <button
                className="pulse-button"
                onClick={fetchPulse}
                disabled={loading}
            >
                {loading ? (
                    <>
                        <div className="pulse-spinner"></div>
                        <span>Analyzing...</span>
                    </>
                ) : (
                    <>
                        <span className="pulse-icon">🔮</span>
                        <span>What's the Pulse?</span>
                    </>
                )}
            </button>

            {error && <div className="pulse-error">⚠️ {error}</div>}

            {/* Use createPortal to render modal at document.body level */}
            {/* This escapes any parent stacking contexts */}
            {showModal && pulseData && createPortal(
                <PulseModal
                    data={pulseData}
                    playerName={playerName}
                    onClose={() => setShowModal(false)}
                />,
                document.body
            )}
        </>
    )
}

export default PulseButton
