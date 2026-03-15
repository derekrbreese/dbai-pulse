import PlayerSearch from './PlayerSearch'
import './DashboardHome.css'

function DashboardHome({ navigate, onPlayerSelect }) {
    const quickActions = [
        {
            id: 'trends',
            icon: '🚀',
            title: 'Breakout Players',
            description: 'Discover players trending up and outperforming projections',
            gradient: 'linear-gradient(135deg, #f59e0b, #ef4444)',
            glow: 'rgba(245, 158, 11, 0.15)',
        },
        {
            id: 'compare',
            icon: '🔄',
            title: 'Compare Players',
            description: 'Head-to-head AI analysis powered by Gemini',
            gradient: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
            glow: 'rgba(99, 102, 241, 0.15)',
        },
        {
            id: 'search',
            icon: '🔍',
            title: 'Player Lookup',
            description: 'Search any player for projections, flags, and Pulse analysis',
            gradient: 'linear-gradient(135deg, #22c55e, #10b981)',
            glow: 'rgba(34, 197, 94, 0.15)',
        },
        {
            id: 'roster',
            icon: '🏈',
            title: 'My Roster',
            description: 'View your Yahoo Fantasy roster with AI-powered insights',
            gradient: 'linear-gradient(135deg, #3b82f6, #06b6d4)',
            glow: 'rgba(59, 130, 246, 0.15)',
        },
        {
            id: 'waiver',
            icon: '📋',
            title: 'Waiver Wire',
            description: 'Find available players worth picking up in your league',
            gradient: 'linear-gradient(135deg, #ec4899, #f97316)',
            glow: 'rgba(236, 72, 153, 0.15)',
        },
    ]

    return (
        <div className="dashboard-home">
            {/* Hero */}
            <div className="home-hero">
                <h1 className="home-title">
                    <span className="home-title-accent">Fantasy Intelligence</span>
                    <span className="home-title-sub">at your fingertips</span>
                </h1>
                <p className="home-subtitle">
                    AI-powered projections, performance flags, and expert analysis
                </p>
            </div>

            {/* Hero Search */}
            <div className="home-search-wrapper">
                <PlayerSearch onPlayerSelect={onPlayerSelect} variant="hero" />
            </div>

            {/* Quick Action Cards */}
            <div className="quick-actions-grid">
                {quickActions.map((action, index) => (
                    <button
                        key={action.id}
                        className="quick-action-card"
                        onClick={() => navigate(action.id)}
                        style={{
                            '--card-glow': action.glow,
                            '--card-gradient': action.gradient,
                            animationDelay: `${index * 0.08}s`,
                        }}
                    >
                        <div className="action-icon-wrapper">
                            <span className="action-icon">{action.icon}</span>
                        </div>
                        <div className="action-content">
                            <h3 className="action-title">{action.title}</h3>
                            <p className="action-description">{action.description}</p>
                        </div>
                        <span className="action-arrow">→</span>
                    </button>
                ))}
            </div>

            {/* Stats Teaser */}
            <div className="home-stats-row">
                <div className="home-stat">
                    <span className="home-stat-value">500+</span>
                    <span className="home-stat-label">Players Tracked</span>
                </div>
                <div className="home-stat">
                    <span className="home-stat-value">7</span>
                    <span className="home-stat-label">Performance Flags</span>
                </div>
                <div className="home-stat">
                    <span className="home-stat-value">AI</span>
                    <span className="home-stat-label">Gemini Powered</span>
                </div>
            </div>
        </div>
    )
}

export default DashboardHome
