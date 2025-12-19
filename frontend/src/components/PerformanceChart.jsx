import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
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

    return (
        <div className="performance-chart">
            <h3 className="chart-title">Last {chartData.length} Weeks</h3>
            <ResponsiveContainer width="100%" height={250}>
                <LineChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                    <XAxis
                        dataKey="week"
                        stroke="rgba(255,255,255,0.5)"
                        tick={{ fill: 'rgba(255,255,255,0.7)', fontSize: 12 }}
                        label={{ value: 'Week', position: 'insideBottom', offset: -5, fill: 'rgba(255,255,255,0.5)' }}
                    />
                    <YAxis
                        stroke="rgba(255,255,255,0.5)"
                        tick={{ fill: 'rgba(255,255,255,0.7)', fontSize: 12 }}
                        label={{ value: 'Points', angle: -90, position: 'insideLeft', fill: 'rgba(255,255,255,0.5)' }}
                    />
                    <Tooltip
                        contentStyle={{
                            backgroundColor: '#1e1e2e',
                            border: '1px solid rgba(255,255,255,0.2)',
                            borderRadius: '8px',
                            color: '#fff'
                        }}
                        labelStyle={{ color: '#a78bfa' }}
                    />
                    <Legend
                        wrapperStyle={{ color: 'rgba(255,255,255,0.7)', fontSize: '12px' }}
                        iconType="line"
                    />
                    <Line
                        type="monotone"
                        dataKey="actual_points"
                        stroke="#22c55e"
                        strokeWidth={3}
                        dot={{ fill: '#22c55e', r: 4 }}
                        activeDot={{ r: 6 }}
                        name="Actual"
                    />
                    <Line
                        type="monotone"
                        dataKey="projected_points"
                        stroke="#6366f1"
                        strokeWidth={2}
                        strokeDasharray="5 5"
                        dot={{ fill: '#6366f1', r: 3 }}
                        name="Projected"
                    />
                </LineChart>
            </ResponsiveContainer>
        </div>
    )
}

// Add missing import
import { useState, useEffect } from 'react'

export default PerformanceChart
