import { useState, useEffect } from 'react'
import './Layout.css'

const NAV_ITEMS = [
    { id: 'home', label: 'Home', icon: '⚡', shortLabel: 'Home' },
    { id: 'search', label: 'Player Search', icon: '🔍', shortLabel: 'Search' },
    { id: 'trends', label: 'Trends & Insights', icon: '📊', shortLabel: 'Trends' },
    { id: 'compare', label: 'Compare Players', icon: '🔄', shortLabel: 'Compare' },
    { id: 'roster', label: 'My Roster', icon: '🏈', shortLabel: 'Roster' },
    { id: 'waiver', label: 'Waiver Wire', icon: '📋', shortLabel: 'Waivers' },
]

function Layout({ children, route, navigate, authUser, onLogout, yahooConnect }) {
    const [sidebarOpen, setSidebarOpen] = useState(false)
    const [collapsed, setCollapsed] = useState(false)

    // Close mobile sidebar on route change
    useEffect(() => {
        setSidebarOpen(false)
    }, [route])

    // Close mobile sidebar on escape
    useEffect(() => {
        const handler = (e) => {
            if (e.key === 'Escape') setSidebarOpen(false)
        }
        window.addEventListener('keydown', handler)
        return () => window.removeEventListener('keydown', handler)
    }, [])

    const handleNavClick = (id) => {
        navigate(id === 'home' ? '' : id)
        setSidebarOpen(false)
    }

    return (
        <div className={`layout ${collapsed ? 'sidebar-collapsed' : ''}`}>
            {/* Mobile overlay */}
            {sidebarOpen && (
                <div
                    className="sidebar-overlay"
                    onClick={() => setSidebarOpen(false)}
                />
            )}

            {/* Sidebar */}
            <aside className={`sidebar ${sidebarOpen ? 'open' : ''}`}>
                <div className="sidebar-header">
                    <div className="sidebar-brand" onClick={() => handleNavClick('home')}>
                        <span className="brand-icon">⚡</span>
                        {!collapsed && (
                            <div className="brand-text">
                                <span className="brand-name"><span className="brand-accent">dbAI</span> Pulse</span>
                                <span className="brand-tagline">Fantasy Intelligence</span>
                            </div>
                        )}
                    </div>
                    <button
                        className="collapse-toggle desktop-only"
                        onClick={() => setCollapsed(!collapsed)}
                        title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
                    >
                        {collapsed ? '»' : '«'}
                    </button>
                </div>

                <nav className="sidebar-nav">
                    {NAV_ITEMS.map((item) => (
                        <button
                            key={item.id}
                            className={`nav-item ${route === item.id ? 'active' : ''}`}
                            onClick={() => handleNavClick(item.id)}
                            title={collapsed ? item.label : undefined}
                        >
                            <span className="nav-icon">{item.icon}</span>
                            {!collapsed && <span className="nav-label">{item.label}</span>}
                            {route === item.id && <span className="nav-indicator" />}
                        </button>
                    ))}
                </nav>

                {/* Yahoo Connect in sidebar */}
                {!collapsed && yahooConnect && (
                    <div className="sidebar-yahoo">
                        {yahooConnect}
                    </div>
                )}

                {/* User section */}
                <div className="sidebar-footer">
                    {authUser ? (
                        <div className="user-section">
                            <div className="user-avatar">
                                {authUser.email?.charAt(0).toUpperCase() || 'U'}
                            </div>
                            {!collapsed && (
                                <div className="user-info">
                                    <span className="user-email" title={authUser.email}>
                                        {authUser.email}
                                    </span>
                                    <button className="logout-btn" onClick={onLogout}>
                                        Log out
                                    </button>
                                </div>
                            )}
                        </div>
                    ) : (
                        !collapsed && (
                            <div className="user-section guest">
                                <span className="guest-label">Not signed in</span>
                            </div>
                        )
                    )}
                </div>
            </aside>

            {/* Main content */}
            <div className="layout-main">
                {/* Mobile header */}
                <header className="mobile-header">
                    <button
                        className="hamburger"
                        onClick={() => setSidebarOpen(!sidebarOpen)}
                        aria-label="Toggle menu"
                    >
                        <span /><span /><span />
                    </button>
                    <div className="mobile-brand">
                        <span className="brand-accent">dbAI</span> Pulse
                    </div>
                    <div className="mobile-header-spacer" />
                </header>

                <main className="content-area">
                    <div className="page-container">
                        {children}
                    </div>
                </main>

                <footer className="app-footer">
                    <p>dbAI Pulse v0.3.0 • Data from Sleeper API • Powered by Gemini 3.1 Flash Lite</p>
                </footer>
            </div>
        </div>
    )
}

export default Layout
