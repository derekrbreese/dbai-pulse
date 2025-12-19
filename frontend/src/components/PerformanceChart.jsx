import { useState, useEffect } from 'react'
import { Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Area, AreaChart } from 'recharts'
import './PerformanceChart.css'

function PerformanceChart({ playerId, playerName }) {
    const [chartData, setChartData] = useState([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)

    useEffect(() => {
        async function fetchTrends() {
            if (!playerId) return

            setLoading(true)
            setError(null)

            try {
                const response = await fetch(`http://localhost:8000/api/players/${playerId}/trends?lookback=5`)
                if (!response.ok) {
                    throw new Error('Failed to fetch trends')
                }
                const data = await response.json()
                setChartData(data.weeks)
            } catch (err) {
                setError(err.message)
            } finally {
                setLoading(false)
            }
        }

        fetchTrends()
    }, [playerId])

    if (loading) {
        return (
            <div className="chart-loading">
                <div className="spinner-small"></div>
                <span>Loading chart...</span>
            </div>
        )
    }

    if (error) {
        return (
            <div className="chart-error">
                ⚠️ Unable to load chart
            </div>
        )
    }

    if (!chartData || chartData.length === 0) {
        return (
            <div className="chart-empty">
                📊 No recent performance data available
            </div>
        )
    }

    const CustomTooltip = ({ active, payload, label }) => {
        if (active && payload && payload.length) {
            return (
                <div className="custom-tooltip">
                    <p className="tooltip-label">Week {label}</p>
                    <p className="tooltip-actual">
                        <span className="dot actual-dot"></span>
                        Actual: <strong>{payload[0].value.toFixed(1)} pts</strong>
                    </p>
                    {payload[1] && payload[1].value > 0 && (
                        <p className="tooltip-projected">
                            <span className="dot projected-dot"></span>
                            Projected: <strong>{payload[1].value.toFixed(1)} pts</strong>
                        </p>
                    )}
                </div>
            )
        }
        return null
    }

    return (
        <div className="performance-chart">
            <div className="chart-header">
                <h3 className="chart-title">📈 Performance Trend</h3>
                <p className="chart-subtitle">Last {chartData.length} Weeks</p>
            </div>
            <ResponsiveContainer width="100%" height={300}>
                <AreaChart data={chartData} margin={{ top: 20, right: 20, left: 0, bottom: 10 }}>
                    <defs>
                        <linearGradient id="colorActual" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#22c55e" stopOpacity={0.3} />
                            <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
                        </linearGradient>
                        <linearGradient id="colorProjected" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#6366f1" stopOpacity={0.2} />
                            <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                        </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                    <XAxis
                        dataKey="week"
                        stroke="rgba(255,255,255,0.3)"
                        tick={{ fill: 'rgba(255,255,255,0.6)', fontSize: 13, fontWeight: 600 }}
                        label={{ value: 'Week', position: 'insideBottom', offset: -8, fill: 'rgba(255,255,255,0.4)' }}
                    />
                    <YAxis
                        stroke="rgba(255,255,255,0.3)"
                        tick={{ fill: 'rgba(255,255,255,0.6)', fontSize: 13, fontWeight: 600 }}
                        label={{ value: 'Points', angle: -90, position: 'insideLeft', fill: 'rgba(255,255,255,0.4)' }}
                    />
                    <Tooltip content={<CustomTooltip />} />
                    <Legend
                        wrapperStyle={{
                            color: 'rgba(255,255,255,0.7)',
                            fontSize: '13px',
                            fontWeight: 600,
                            paddingTop: '20px'
                        }}
                        iconType="line"
                    />
                    <Area
                        type="monotone"
                        dataKey="actual_points"
                        stroke="#22c55e"
                        strokeWidth={3}
                        fill="url(#colorActual)"
                        fillOpacity={1}
                        dot={{ fill: '#22c55e', r: 5, strokeWidth: 2, stroke: '#15803d' }}
                        activeDot={{ r: 7, strokeWidth: 0, fill: '#22c55e' }}
                        name="Actual"
                    />
                    <Line
                        type="monotone"
                        dataKey="projected_points"
                        stroke="#6366f1"
                        strokeWidth={2}
                        strokeDasharray="5 5"
                        dot={{ fill: '#6366f1', r: 4, strokeWidth: 2, stroke: '#4f46e5' }}
                        activeDot={{ r: 6 }}
                        name="Projected"
                    />
                </AreaChart>
            </ResponsiveContainer>
        </div>
    )
}

export default PerformanceChart
