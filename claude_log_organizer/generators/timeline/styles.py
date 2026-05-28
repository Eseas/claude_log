"""Style constants, layout parameters, and the ProcessStep dataclass."""

from dataclasses import dataclass, field
from typing import List


@dataclass
class ProcessStep:
    """A single process step with type classification."""
    type: str  # analysis, decision, implementation, verification, summary
    summary: str
    details: List[str] = field(default_factory=list)


# Step type visual config: (fill_color, stroke_color, icon)
STEP_TYPE_STYLES = {
    "analysis":       ("#e1f5fe", "#0288d1", "🔍"),  # light blue
    "decision":       ("#fff8e1", "#f9a825", "⚡"),  # amber/yellow
    "implementation": ("#e8f5e9", "#388e3c", "🔧"),  # green
    "verification":   ("#f3e5f5", "#7b1fa2", "✅"),  # purple
    "summary":        ("#efebe9", "#5d4037", "📋"),  # brown/gray
}


# Session color palette
COLORS = [
    ("#dae8fc", "#6c8ebf"),  # blue
    ("#d5e8d4", "#82b366"),  # green
    ("#fff2cc", "#d6b656"),  # yellow
    ("#f8cecc", "#b85450"),  # red
    ("#e1d5e7", "#9673a6"),  # purple
    ("#ffe6cc", "#d79b00"),  # orange
]

# Gantt layout constants
TITLE_Y = 20
TITLE_HEIGHT = 40
TIME_AXIS_Y = 80
TIME_AXIS_HEIGHT = 25
SESSION_LABEL_WIDTH = 120
TIME_AREA_X = 140
ROW_HEIGHT = 70
BAR_HEIGHT = 36
BAR_Y_OFFSET = 22
BAR_LANE_GAP = 4
ROW_BOTTOM_PADDING = 16
PX_PER_MINUTE = 4
MIN_BAR_WIDTH = 50

# Per-entry page layout constants
ENTRY_PAGE_WIDTH = 520
ENTRY_PAGE_LEFT_MARGIN = 30
ENTRY_BOX_WIDTH = 450
ENTRY_BOX_MIN_HEIGHT = 60
ENTRY_LINE_HEIGHT = 16
ENTRY_V_GAP = 10
ENTRY_ARROW_GAP = 20
ENTRY_TITLE_HEIGHT = 50
ENTRY_META_HEIGHT = 30
ENTRY_TAB_MAX_CHARS = 40
