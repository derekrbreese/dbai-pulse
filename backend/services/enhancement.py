"""
Enhancement Engine for dbAI Pulse.

Responsible for calculating performance flags and adjusted projections
based on Sleeper data and recent performance trends.
"""

from typing import List
import logging
from models.schemas import RecentPerformance

logger = logging.getLogger(__name__)


class EnhancementEngine:
    """Calculates flags and adjusts projections."""

    @staticmethod
    def calculate_flags(projection: float, recent: RecentPerformance) -> List[str]:
        """
        Calculate performance flags based on projection vs recent performance.

        Rules:
        - BREAKOUT_CANDIDATE: L3W avg > 150% of projection
        - TRENDING_UP: L3W avg > 120% of projection
        - UNDERPERFORMING: L3W avg < 80% of projection
        - DECLINING_ROLE: L3W avg < 70% of projection
        - HIGH_CEILING: Best week > 200% of projection
        - BOOM_BUST: Best week > 2x Worst week (and analyzed > 1 week)
        - CONSISTENT: All weeks within +/- 20% of avg (and analyzed > 1 week)
        """
        flags = []

        if recent.weeks_analyzed == 0 or projection == 0:
            return flags

        l3w_avg = recent.avg_points
        max_score = max(recent.weekly_points) if recent.weekly_points else 0
        min_score = min(recent.weekly_points) if recent.weekly_points else 0

        # Breakout / Trending
        if l3w_avg >= projection * 1.5:
            flags.append("BREAKOUT_CANDIDATE")
        elif l3w_avg >= projection * 1.2:
            flags.append("TRENDING_UP")

        # Declining / Underperforming
        if l3w_avg <= projection * 0.7:
            flags.append("DECLINING_ROLE")
        elif l3w_avg <= projection * 0.8:
            flags.append("UNDERPERFORMING")

        # Ceiling
        if max_score >= projection * 2.0:
            flags.append("HIGH_CEILING")

        # Volatility
        if recent.weeks_analyzed >= 2:
            if max_score >= min_score * 2.0 and min_score > 0:
                flags.append("BOOM_BUST")

            # Consistency check
            is_consistent = all(
                abs(score - l3w_avg) <= (l3w_avg * 0.2)
                for score in recent.weekly_points
            )
            if is_consistent:
                flags.append("CONSISTENT")

        return flags

    @staticmethod
    def calculate_adjusted_projection(
        base_projection: float, recent: RecentPerformance, flags: List[str]
    ) -> float:
        """
        Calculate adjusted projection based on flags and trends.
        """
        if recent.weeks_analyzed == 0 or base_projection == 0:
            return base_projection

        # Weights for blending
        # Default: 100% Sleeper
        weight_recent = 0.0

        if "BREAKOUT_CANDIDATE" in flags:
            weight_recent = 0.4  # Trust the breakout logic significantly
        elif "TRENDING_UP" in flags:
            weight_recent = 0.2  # Slight bias to recent
        elif "DECLINING_ROLE" in flags:
            weight_recent = 0.3  # Trust the decline
        elif "UNDERPERFORMING" in flags:
            weight_recent = 0.15

        # Calculate blended projection
        # Valid constraint: Adjusted shouldn't be wildly different from base (cap at +/- 50% change?)
        # For now, simple weighted avg

        adjusted = (base_projection * (1.0 - weight_recent)) + (
            recent.avg_points * weight_recent
        )

        return round(adjusted, 1)


def get_enhancement_engine() -> EnhancementEngine:
    return EnhancementEngine()
