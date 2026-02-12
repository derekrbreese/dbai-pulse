import { useState } from 'react'
import './PlayerHeadshot.css'

const POSITION_COLORS = {
    QB: '#e74c3c',
    RB: '#27ae60',
    WR: '#3498db',
    TE: '#f39c12',
    K: '#9b59b6',
    DEF: '#34495e',
}

function PlayerHeadshot({ espnId, position, size = 48 }) {
    const [imgError, setImgError] = useState(false)
    const color = POSITION_COLORS[position] || '#7f8c8d'

    if (!espnId || imgError) {
        const fontSize = size < 32 ? '0.65rem' : size < 40 ? '0.75rem' : '1.25rem'
        return (
            <span
                className="headshot-fallback"
                style={{
                    width: size,
                    height: size,
                    backgroundColor: color,
                    fontSize,
                }}
            >
                {position}
            </span>
        )
    }

    return (
        <img
            className="player-headshot"
            src={`https://a.espncdn.com/i/headshots/nfl/players/full/${espnId}.png`}
            alt={position}
            width={size}
            height={size}
            style={{ borderColor: color }}
            onError={() => setImgError(true)}
        />
    )
}

export default PlayerHeadshot
