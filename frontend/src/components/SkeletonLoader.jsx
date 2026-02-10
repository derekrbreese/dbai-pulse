import './SkeletonLoader.css'

function SkeletonLine({ width = '100%', height = '14px' }) {
    return <div className="skeleton-line" style={{ width, height }} />
}

export function PlayerCardSkeleton() {
    return (
        <div className="skeleton-card">
            {/* Header */}
            <div className="skeleton-header">
                <div className="skeleton-avatar" />
                <div className="skeleton-header-text">
                    <SkeletonLine width="140px" height="18px" />
                    <SkeletonLine width="60px" height="12px" />
                </div>
            </div>

            {/* Projection */}
            <div className="skeleton-section">
                <SkeletonLine width="80px" height="10px" />
                <SkeletonLine width="100px" height="36px" />
            </div>

            {/* Stats grid */}
            <div className="skeleton-section">
                <SkeletonLine width="120px" height="10px" />
                <div className="skeleton-stats-grid">
                    <div className="skeleton-stat">
                        <SkeletonLine width="50px" height="20px" />
                        <SkeletonLine width="40px" height="10px" />
                    </div>
                    <div className="skeleton-stat">
                        <SkeletonLine width="30px" height="20px" />
                        <SkeletonLine width="40px" height="10px" />
                    </div>
                    <div className="skeleton-stat">
                        <SkeletonLine width="40px" height="20px" />
                        <SkeletonLine width="50px" height="10px" />
                    </div>
                </div>
            </div>

            {/* Flags */}
            <div className="skeleton-section">
                <SkeletonLine width="120px" height="10px" />
                <div className="skeleton-flags">
                    <SkeletonLine width="90px" height="24px" />
                    <SkeletonLine width="110px" height="24px" />
                    <SkeletonLine width="80px" height="24px" />
                </div>
            </div>
        </div>
    )
}

export function ChartSkeleton() {
    return (
        <div className="skeleton-chart">
            <div className="skeleton-chart-header">
                <SkeletonLine width="180px" height="16px" />
                <SkeletonLine width="100px" height="12px" />
            </div>
            <div className="skeleton-chart-area">
                <div className="skeleton-chart-bars">
                    {[65, 45, 80, 55, 70].map((h, i) => (
                        <div key={i} className="skeleton-bar" style={{ height: `${h}%` }} />
                    ))}
                </div>
            </div>
        </div>
    )
}
