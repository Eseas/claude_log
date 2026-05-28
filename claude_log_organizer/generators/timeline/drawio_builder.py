"""draw.io XML construction — Gantt page and per-entry detail pages."""

import xml.etree.ElementTree as ET
from collections import OrderedDict
from datetime import datetime, timedelta
from typing import List, Dict, Tuple

from claude_log_organizer.models.task_data import TimelineEntry, ProcessPhase
from claude_log_organizer.generators.timeline.styles import (
    ProcessStep, STEP_TYPE_STYLES, COLORS,
    TITLE_Y, TITLE_HEIGHT, TIME_AXIS_Y, TIME_AXIS_HEIGHT,
    SESSION_LABEL_WIDTH, TIME_AREA_X, ROW_HEIGHT,
    BAR_HEIGHT, BAR_Y_OFFSET, BAR_LANE_GAP, ROW_BOTTOM_PADDING,
    PX_PER_MINUTE, MIN_BAR_WIDTH,
    ENTRY_PAGE_WIDTH, ENTRY_PAGE_LEFT_MARGIN, ENTRY_BOX_WIDTH,
    ENTRY_BOX_MIN_HEIGHT, ENTRY_LINE_HEIGHT, ENTRY_V_GAP,
    ENTRY_ARROW_GAP, ENTRY_TITLE_HEIGHT, ENTRY_META_HEIGHT,
    ENTRY_TAB_MAX_CHARS,
)


def build_drawio_xml(
    merged_entries: List[TimelineEntry],
    all_entries: List[TimelineEntry],
    title: str,
) -> str:
    """Build .drawio with Page 1 (Gantt) and per-entry pages (Process Flow)."""
    mxfile = ET.Element("mxfile", host="Claude Log Organizer")

    # Page 1: Gantt Timeline
    build_gantt_page(mxfile, merged_entries, title)

    # Pages 2..N: One page per merged entry
    sessions_seen: List[str] = []
    for entry in merged_entries:
        if entry.session_short not in sessions_seen:
            sessions_seen.append(entry.session_short)

    for entry_idx, entry in enumerate(merged_entries):
        session_idx = sessions_seen.index(entry.session_short)
        color_fill, color_stroke = COLORS[session_idx % len(COLORS)]
        build_entry_page(mxfile, entry, entry_idx, color_fill, color_stroke)

    ET.indent(mxfile, space="  ")
    return ET.tostring(mxfile, encoding="unicode", xml_declaration=True)


def assign_lanes(entries: List[TimelineEntry], axis_start: datetime) -> List[int]:
    """Assign lanes to entries to avoid visual overlap on the Gantt chart.

    Returns a list of lane indices (0-based), one per entry.
    Entries that don't overlap share lane 0; overlapping ones go to higher lanes.
    """
    lanes: List[List[Tuple[int, int]]] = []  # each lane: list of (bar_x, bar_end_x)
    result: List[int] = []
    for entry in entries:
        bar_x = time_to_x(entry.start_time, axis_start)
        bar_end_x = time_to_x(entry.end_time, axis_start)
        bar_end_x = max(bar_end_x, bar_x + MIN_BAR_WIDTH)

        assigned = False
        for lane_idx, lane in enumerate(lanes):
            overlap = any(bar_x < lex and bar_end_x > lx for lx, lex in lane)
            if not overlap:
                lane.append((bar_x, bar_end_x))
                result.append(lane_idx)
                assigned = True
                break

        if not assigned:
            lanes.append([(bar_x, bar_end_x)])
            result.append(len(lanes) - 1)

    return result


def build_gantt_page(mxfile: ET.Element, entries: List[TimelineEntry], title: str):
    """Build the Gantt timeline page."""
    min_time = min(e.start_time for e in entries)
    max_time = max(e.end_time for e in entries)

    axis_start = min_time.replace(minute=(min_time.minute // 30) * 30, second=0, microsecond=0)
    axis_end_minute = max_time.minute
    if axis_end_minute % 30 != 0:
        axis_end = max_time.replace(minute=0, second=0, microsecond=0) + timedelta(minutes=((axis_end_minute // 30) + 1) * 30)
    else:
        axis_end = max_time.replace(second=0, microsecond=0)
    axis_end += timedelta(minutes=30)

    sessions: Dict[str, List[TimelineEntry]] = OrderedDict()
    for entry in entries:
        if entry.session_short not in sessions:
            sessions[entry.session_short] = []
        sessions[entry.session_short].append(entry)

    total_minutes = (axis_end - axis_start).total_seconds() / 60
    time_axis_width = int(total_minutes * PX_PER_MINUTE)
    page_width = TIME_AREA_X + time_axis_width + 40
    rows_start_y = TIME_AXIS_Y + TIME_AXIS_HEIGHT + 10

    # Pre-compute lanes for overlap detection and dynamic row heights
    session_lanes: Dict[str, List[int]] = {}
    session_max_lanes: Dict[str, int] = {}
    session_row_heights: Dict[str, int] = {}
    session_row_y: Dict[str, int] = {}
    cumulative_y = rows_start_y
    for session_short, session_entries in sessions.items():
        lanes = assign_lanes(session_entries, axis_start)
        session_lanes[session_short] = lanes
        max_l = (max(lanes) + 1) if lanes else 1
        session_max_lanes[session_short] = max_l
        row_h = BAR_Y_OFFSET + max_l * BAR_HEIGHT + (max_l - 1) * BAR_LANE_GAP + ROW_BOTTOM_PADDING
        session_row_heights[session_short] = row_h
        session_row_y[session_short] = cumulative_y
        cumulative_y += row_h
    total_rows_height = cumulative_y - rows_start_y
    page_height = cumulative_y + 40

    diagram = ET.SubElement(mxfile, "diagram", name="Timeline", id="gantt")
    graph_model = ET.SubElement(
        diagram, "mxGraphModel",
        dx=str(page_width), dy=str(page_height),
        grid="1", gridSize="10", guides="1", tooltips="1",
        connect="0", arrows="0", fold="1", page="1", pageScale="1",
        pageWidth=str(page_width), pageHeight=str(page_height),
    )
    root = ET.SubElement(graph_model, "root")
    ET.SubElement(root, "mxCell", id="0")
    ET.SubElement(root, "mxCell", id="1", parent="0")
    cell_id = 2

    # Title
    cell_id = add_cell(root, cell_id, title,
        "text;html=1;align=center;verticalAlign=middle;resizable=0;points=[];autosize=1;strokeColor=none;fillColor=none;fontSize=18;fontStyle=1;",
        (page_width - 400) // 2, TITLE_Y, 400, TITLE_HEIGHT)

    # Time axis line
    cell_id = add_cell(root, cell_id, "",
        "line;strokeWidth=2;strokeColor=#666666;fillColor=none;align=left;verticalAlign=middle;spacingTop=-1;spacingLeft=3;spacingRight=3;rotatable=0;labelPosition=left;points=[];portConstraint=eastwest;",
        TIME_AREA_X, TIME_AXIS_Y + TIME_AXIS_HEIGHT, time_axis_width, 1)

    # Time ticks and gridlines
    current_time = axis_start
    while current_time <= axis_end:
        x_pos = time_to_x(current_time, axis_start)
        cell_id = add_cell(root, cell_id, current_time.strftime("%H:%M"),
            "text;html=1;align=center;verticalAlign=bottom;resizable=0;points=[];autosize=1;strokeColor=none;fillColor=none;fontSize=11;fontColor=#666666;",
            x_pos - 20, TIME_AXIS_Y, 40, TIME_AXIS_HEIGHT)
        cell_id = add_cell(root, cell_id, "",
            "line;strokeWidth=1;strokeColor=#EEEEEE;fillColor=none;direction=south;",
            x_pos, rows_start_y, 1, total_rows_height)
        current_time += timedelta(minutes=30)

    # Session rows and bars
    for session_idx, (session_short, session_entries) in enumerate(sessions.items()):
        color_fill, color_stroke = COLORS[session_idx % len(COLORS)]
        row_y = session_row_y[session_short]
        row_height = session_row_heights[session_short]
        lanes = session_lanes[session_short]

        cell_id = add_cell(root, cell_id, session_short,
            f"text;html=1;align=right;verticalAlign=middle;resizable=0;points=[];autosize=1;strokeColor=none;fillColor=none;fontSize=11;fontStyle=1;fontColor={color_stroke};",
            0, row_y + BAR_Y_OFFSET - 5, SESSION_LABEL_WIDTH, 30)

        if session_idx % 2 == 0:
            cell_id = add_cell(root, cell_id, "",
                "rounded=0;whiteSpace=wrap;html=1;fillColor=#F9F9F9;strokeColor=none;opacity=50;",
                TIME_AREA_X, row_y, time_axis_width, row_height)

        for entry_local_idx, entry in enumerate(session_entries):
            lane = lanes[entry_local_idx]
            bar_x = time_to_x(entry.start_time, axis_start)
            bar_end_x = time_to_x(entry.end_time, axis_start)
            bar_width = max(bar_end_x - bar_x, MIN_BAR_WIDTH)
            bar_y = row_y + BAR_Y_OFFSET + lane * (BAR_HEIGHT + BAR_LANE_GAP)
            time_range = f"{entry.start_time.strftime('%H:%M')} - {entry.end_time.strftime('%H:%M')}"

            bar_label = entry.label
            tooltip_lines = [entry.label, time_range, entry.task_file]
            if entry.process_phases:
                tooltip_lines.append("")
                tooltip_lines.append("[Work Phases]")
                for phase in entry.process_phases:
                    icon = STEP_TYPE_STYLES.get(phase.primary_type, STEP_TYPE_STYLES["analysis"])[2]
                    tooltip_lines.append(f"  {icon} {phase.phase_name} ({phase.step_count} steps)")
            elif entry.process_steps:
                tooltip_lines.append("")
                for i, step in enumerate(entry.process_steps, 1):
                    if isinstance(step, ProcessStep):
                        icon = STEP_TYPE_STYLES.get(step.type, STEP_TYPE_STYLES["analysis"])[2]
                        tooltip_lines.append(f"{i}. {icon} [{step.type}] {step.summary}")
                    else:
                        tooltip_lines.append(f"{i}. {step}")
            if entry.thinking_summary:
                tooltip_lines.append("")
                tooltip_lines.append("[Thinking]")
                for t in entry.thinking_summary:
                    tooltip_lines.append(f"  - {t}")
            if entry.referenced_documents:
                tooltip_lines.append("")
                tooltip_lines.append("[Documents]")
                for d in entry.referenced_documents:
                    tooltip_lines.append(f"  - {d}")

            # Dashed border for tasks with context compression
            bar_style = f"rounded=1;whiteSpace=wrap;html=1;fillColor={color_fill};strokeColor={color_stroke};fontSize=10;fontColor=#333333;align=left;verticalAlign=middle;spacingLeft=6;overflow=hidden;"
            if entry.compact_count > 0:
                bar_style += "dashed=1;dashPattern=5 3;"

            cell_id = add_cell(root, cell_id, bar_label,
                bar_style,
                bar_x, bar_y, bar_width, BAR_HEIGHT,
                tooltip="\n".join(tooltip_lines))

            cell_id = add_cell(root, cell_id, time_range,
                "text;html=1;align=left;verticalAlign=top;resizable=0;points=[];autosize=1;strokeColor=none;fillColor=none;fontSize=8;fontColor=#999999;",
                bar_x, bar_y + BAR_HEIGHT, bar_width, 14)


def estimate_box_height(text_lines: int) -> int:
    """Estimate box height based on number of text lines."""
    return max(ENTRY_BOX_MIN_HEIGHT, 30 + text_lines * ENTRY_LINE_HEIGHT)


def build_entry_page(
    mxfile: ET.Element,
    entry: TimelineEntry,
    entry_idx: int,
    color_fill: str,
    color_stroke: str,
) -> None:
    """Build a single draw.io page for one entry with vertical phase/step flow."""
    # Page tab name: max 40 chars, word-boundary truncation (no ellipsis)
    tab_name = entry.label
    if len(tab_name) > ENTRY_TAB_MAX_CHARS:
        cut = tab_name[:ENTRY_TAB_MAX_CHARS].rfind(' ')
        tab_name = tab_name[:cut] if cut > 20 else tab_name[:ENTRY_TAB_MAX_CHARS]

    diagram_id = f"entry_{entry_idx}"
    diagram = ET.SubElement(mxfile, "diagram", name=tab_name, id=diagram_id)

    graph_model = ET.SubElement(
        diagram, "mxGraphModel",
        dx=str(ENTRY_PAGE_WIDTH), dy="2000",
        grid="1", gridSize="10", guides="1", tooltips="1",
        connect="1", arrows="1", fold="1", page="1", pageScale="1",
        pageWidth=str(ENTRY_PAGE_WIDTH), pageHeight="2000",
    )
    root = ET.SubElement(graph_model, "root")
    ET.SubElement(root, "mxCell", id="0")
    ET.SubElement(root, "mxCell", id="1", parent="0")

    # Cell ID offset to avoid collisions across pages
    cell_id = 2 + (entry_idx + 1) * 10000

    y_cursor = 20

    # --- Title ---
    cell_id = add_cell(root, cell_id, f"<b>{entry.label}</b>",
        "text;html=1;align=left;verticalAlign=middle;resizable=0;points=[];autosize=1;"
        "strokeColor=none;fillColor=none;fontSize=14;fontStyle=1;whiteSpace=wrap;",
        ENTRY_PAGE_LEFT_MARGIN, y_cursor, ENTRY_BOX_WIDTH, ENTRY_TITLE_HEIGHT)
    y_cursor += ENTRY_TITLE_HEIGHT

    # --- Meta: time + session ---
    time_str = f"{entry.start_time.strftime('%H:%M')} - {entry.end_time.strftime('%H:%M')}"
    meta_text = f"Session {entry.session_short} | {time_str}"
    if entry.compact_count > 0:
        meta_text += f" | compact x{entry.compact_count}"
    cell_id = add_cell(root, cell_id, meta_text,
        f"text;html=1;align=left;verticalAlign=middle;resizable=0;points=[];autosize=1;"
        f"strokeColor=none;fillColor=none;fontSize=10;fontColor={color_stroke};",
        ENTRY_PAGE_LEFT_MARGIN, y_cursor, ENTRY_BOX_WIDTH, ENTRY_META_HEIGHT)
    y_cursor += ENTRY_META_HEIGHT + 10

    # --- Referenced documents ---
    if entry.referenced_documents:
        for doc in entry.referenced_documents:
            cell_id = add_cell(root, cell_id,
                f"📄 {doc}",
                "rounded=1;whiteSpace=wrap;html=1;fillColor=#f5f5f5;strokeColor=#cccccc;"
                "fontSize=9;fontColor=#666666;fontStyle=2;align=left;verticalAlign=middle;spacingLeft=6;",
                ENTRY_PAGE_LEFT_MARGIN, y_cursor, ENTRY_BOX_WIDTH, 26)
            y_cursor += 30
        y_cursor += 5

    # --- Legend ---
    legend_x = ENTRY_PAGE_LEFT_MARGIN
    for step_type, (fill, stroke, icon) in STEP_TYPE_STYLES.items():
        legend_style = (
            f"rounded=1;whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};"
            f"fontSize=8;fontColor=#333333;align=center;verticalAlign=middle;"
        )
        cell_id = add_cell(root, cell_id,
            f"{icon} {step_type.capitalize()}",
            legend_style,
            legend_x, y_cursor, 88, 20)
        legend_x += 95
    y_cursor += 30

    # --- Phase/Step vertical flow ---
    items = entry.process_phases if entry.process_phases else entry.process_steps
    prev_cell_id = None

    if items:
        for idx, item in enumerate(items):
            if isinstance(item, ProcessPhase):
                fill, stroke, icon = STEP_TYPE_STYLES.get(item.primary_type, STEP_TYPE_STYLES["analysis"])

                label_parts = [f"<b>{icon} {idx + 1}. {item.phase_name}</b>"]
                label_parts.append(
                    f"<br/><font style='font-size:9px' color='#666666'>"
                    f"({item.step_count} steps, {item.primary_type})</font>"
                )
                label_parts.append(f"<br/>{item.summary}")
                for detail in item.key_details:
                    label_parts.append(
                        f"<br/><font style='font-size:8px' color='#555555'>- {detail}</font>"
                    )

                label = "".join(label_parts)
                text_lines = 3 + len(item.key_details)
                box_height = estimate_box_height(text_lines)
                item_type = item.primary_type

            elif isinstance(item, ProcessStep):
                fill, stroke, icon = STEP_TYPE_STYLES.get(item.type, STEP_TYPE_STYLES["analysis"])

                label_parts = [f"<b>{icon} {idx + 1}. {item.summary}</b>"]
                for detail in item.details:
                    label_parts.append(
                        f"<br/><font style='font-size:8px' color='#555555'>- {detail}</font>"
                    )

                label = "".join(label_parts)
                text_lines = 1 + len(item.details)
                box_height = estimate_box_height(text_lines)
                item_type = item.type

            else:
                label = f"<b>{idx + 1}.</b> {item}"
                box_height = ENTRY_BOX_MIN_HEIGHT
                item_type = "analysis"
                fill, stroke, icon = STEP_TYPE_STYLES["analysis"]

            # Style by type
            if item_type == "decision":
                style = (
                    f"shape=hexagon;perimeter=hexagonPerimeter2;whiteSpace=wrap;html=1;"
                    f"fixedSize=1;size=10;fillColor={fill};strokeColor={stroke};strokeWidth=2;"
                    f"fontSize=9;fontColor=#333333;align=left;verticalAlign=top;"
                    f"spacingLeft=12;spacingRight=12;spacingTop=6;"
                )
            elif item_type == "verification":
                style = (
                    f"rounded=1;whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};"
                    f"strokeWidth=2;fontSize=9;fontColor=#333333;align=left;verticalAlign=top;"
                    f"spacingLeft=6;spacingRight=6;spacingTop=6;dashed=1;dashPattern=3 2;"
                )
            else:
                style = (
                    f"rounded=1;whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};"
                    f"strokeWidth=1;fontSize=9;fontColor=#333333;align=left;verticalAlign=top;"
                    f"spacingLeft=6;spacingRight=6;spacingTop=6;"
                )

            current_cell_id = cell_id
            cell_id = add_cell(root, cell_id, label, style,
                ENTRY_PAGE_LEFT_MARGIN, y_cursor, ENTRY_BOX_WIDTH, box_height)

            if prev_cell_id is not None:
                cell_id = add_edge(root, cell_id, prev_cell_id, current_cell_id,
                                         color_stroke, vertical=True)

            prev_cell_id = current_cell_id
            y_cursor += box_height + ENTRY_ARROW_GAP

    # --- Thinking summary ---
    if entry.thinking_summary:
        y_cursor += 10
        cell_id = add_cell(root, cell_id, "<b>Thinking / Reasoning</b>",
            "text;html=1;align=left;verticalAlign=middle;resizable=0;points=[];autosize=1;"
            "strokeColor=none;fillColor=none;fontSize=11;fontStyle=1;fontColor=#777777;",
            ENTRY_PAGE_LEFT_MARGIN, y_cursor, ENTRY_BOX_WIDTH, 24)
        y_cursor += 28

        for thought in entry.thinking_summary:
            thought_lines = max(1, len(thought) // 70 + 1)
            thought_height = max(24, thought_lines * ENTRY_LINE_HEIGHT + 8)
            cell_id = add_cell(root, cell_id,
                f"<i>💭 {thought}</i>",
                "rounded=1;whiteSpace=wrap;html=1;fillColor=#fafafa;strokeColor=#e0e0e0;"
                "fontSize=9;fontColor=#666666;fontStyle=2;align=left;verticalAlign=top;"
                "spacingLeft=6;spacingRight=6;spacingTop=4;",
                ENTRY_PAGE_LEFT_MARGIN, y_cursor, ENTRY_BOX_WIDTH, thought_height)
            y_cursor += thought_height + 6

    # --- Files modified ---
    if entry.files_modified:
        y_cursor += 10
        cell_id = add_cell(root, cell_id, "<b>Files Modified</b>",
            "text;html=1;align=left;verticalAlign=middle;resizable=0;points=[];autosize=1;"
            "strokeColor=none;fillColor=none;fontSize=11;fontStyle=1;fontColor=#777777;",
            ENTRY_PAGE_LEFT_MARGIN, y_cursor, ENTRY_BOX_WIDTH, 24)
        y_cursor += 28

        files_label = "<br/>".join(f"- {f}" for f in entry.files_modified)
        files_height = max(30, len(entry.files_modified) * ENTRY_LINE_HEIGHT + 12)
        cell_id = add_cell(root, cell_id, files_label,
            "rounded=1;whiteSpace=wrap;html=1;fillColor=#f0f4f8;strokeColor=#b0bec5;"
            "fontSize=9;fontColor=#37474f;align=left;verticalAlign=top;"
            "spacingLeft=6;spacingRight=6;spacingTop=4;",
            ENTRY_PAGE_LEFT_MARGIN, y_cursor, ENTRY_BOX_WIDTH, files_height)
        y_cursor += files_height + 10

    # --- Finalize page height ---
    actual_height = y_cursor + 30
    graph_model.set("dy", str(actual_height))
    graph_model.set("pageHeight", str(actual_height))


# ===== Helpers =====

def time_to_x(dt: datetime, axis_start: datetime) -> int:
    minutes = (dt - axis_start).total_seconds() / 60
    return TIME_AREA_X + int(minutes * PX_PER_MINUTE)


def add_cell(root, cell_id, value, style, x, y, width, height, tooltip=""):
    attrs = {
        "id": str(cell_id), "value": value, "style": style,
        "vertex": "1", "parent": "1",
    }
    if tooltip:
        attrs["tooltip"] = tooltip
    cell = ET.SubElement(root, "mxCell", **attrs)
    ET.SubElement(cell, "mxGeometry", x=str(x), y=str(y),
                  width=str(width), height=str(height), **{"as": "geometry"})
    return cell_id + 1


def add_edge(root, cell_id, source_id, target_id, color, vertical=False):
    style = f"edgeStyle=orthogonalEdgeStyle;rounded=1;strokeColor={color};"
    if vertical:
        style += "exitX=0.5;exitY=1;exitDx=0;exitDy=0;entryX=0.5;entryY=0;entryDx=0;entryDy=0;"
    ET.SubElement(root, "mxCell", **{
        "id": str(cell_id),
        "value": "",
        "style": style,
        "edge": "1", "parent": "1",
        "source": str(source_id), "target": str(target_id),
    })
    return cell_id + 1
