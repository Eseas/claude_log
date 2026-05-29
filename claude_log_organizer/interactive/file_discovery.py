"""File and log discovery utilities for the interactive CLI."""

import re
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import inquirer

from claude_log_organizer.config import Config
from claude_log_organizer.output import out


def format_size(size_bytes: int) -> str:
    """Format file size in human-readable format.

    Args:
        size_bytes: Size in bytes

    Returns:
        Formatted size string
    """
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f}KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f}MB"


def extract_date_from_filename(filename: str) -> Optional[date]:
    """Extract date from task filename.

    Handles format: task-YYYY-MM-DD_HHMMSS_UUID.md

    Args:
        filename: Task file name

    Returns:
        date object or None if date cannot be extracted
    """
    match = re.match(r'task-(\d{4})-(\d{2})-(\d{2})_', filename)
    if match:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    return None


def discover_project_task_files(config_path: Path) -> List[Path]:
    """Discover task files from all project directories in watch config.

    For each watch directory (e.g. {project}/.claude/logs), derives the project
    root and looks for task-*.md files in {project}/tasks/.
    Falls back to config's output.directory if no project tasks are found.

    Args:
        config_path: Path to configuration file

    Returns:
        List of task file Paths
    """
    config = Config(config_path) if config_path.exists() else Config(None)
    watch_dirs = config.get("watch.directories", [])
    if isinstance(watch_dirs, str):
        watch_dirs = [watch_dirs]

    task_files = []
    seen: set = set()

    for wd_str in watch_dirs:
        wd = Path(wd_str).expanduser()
        # Derive project root: {project}/.claude/logs -> {project}
        if wd.name == "logs" and wd.parent.name == ".claude":
            project_root = wd.parent.parent
        else:
            project_root = wd.parent

        tasks_dir = project_root / "tasks"
        if tasks_dir.exists():
            for f in tasks_dir.glob("task-*.md"):
                key = str(f.resolve())
                if key not in seen:
                    seen.add(key)
                    task_files.append(f)

    # Fallback to config output.directory
    if not task_files:
        output_dir = Path(config.get("output.directory", "./tasks"))
        task_files = list(output_dir.glob("task-*.md"))

    return task_files


def group_files_by_session(task_files: List[Path]) -> dict:
    """Group task files by session ID.

    Args:
        task_files: List of task markdown files

    Returns:
        Dictionary mapping session ID to list of files
    """
    sessions = {}
    for file in task_files:
        # Extract session ID from filename: task-YYYY-MM-DD_HHMMSS_session-id.md
        # or task-session-id.md
        match = re.search(r'task-(?:\d{4}-\d{2}-\d{2}_\d{6}_)?([a-f0-9-]+)\.md', file.name)
        if match:
            session_id = match.group(1)
            if session_id not in sessions:
                sessions[session_id] = []
            sessions[session_id].append(file)

    return sessions


def group_files_by_date(task_files: List[Path]) -> Dict[date, List[Path]]:
    """Group task files by date extracted from filename.

    Args:
        task_files: List of task markdown files

    Returns:
        Dictionary mapping date to list of files, sorted by date
    """
    date_groups = defaultdict(list)
    for f in task_files:
        file_date = extract_date_from_filename(f.name)
        if file_date:
            date_groups[file_date].append(f)

    for d in date_groups:
        date_groups[d].sort(key=lambda x: x.name)

    return dict(sorted(date_groups.items()))


def find_log_files_for_sessions(session_ids: List[str], config_path: Path) -> List[Path]:
    """Find .log files matching given session IDs across all watch directories.

    Args:
        session_ids: List of session IDs to search for
        config_path: Path to configuration file

    Returns:
        List of matching log file Paths
    """
    config = Config(config_path) if config_path.exists() else Config(None)

    # Collect all log directories from watch config
    watch_dirs = config.get("watch.directories", [])
    if isinstance(watch_dirs, str):
        watch_dirs = [watch_dirs]

    log_dirs: List[Path] = [Path(wd).expanduser() for wd in watch_dirs]

    # Add fallback from input.log_directory config
    fallback = Path(config.get("input.log_directory", ".claude/logs"))
    if fallback not in log_dirs:
        log_dirs.append(fallback)

    log_files = []
    seen: set = set()

    for log_dir in log_dirs:
        if not log_dir.exists():
            continue
        for log_file in sorted(log_dir.glob("*.log")):
            key = str(log_file.resolve())
            if key in seen:
                continue
            for sid in session_ids:
                if sid in log_file.name:
                    seen.add(key)
                    log_files.append(log_file)
                    break

    return log_files


def find_log_files_for_task_files(task_files: List[Path], config_path: Path) -> List[Path]:
    """Find .log files that correspond to given task files (by session ID).

    Args:
        task_files: List of task file Paths
        config_path: Path to configuration file

    Returns:
        List of matching log file Paths
    """
    session_ids = set()
    project_roots = set()
    for tf in task_files:
        match = re.search(r'([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})', tf.name)
        if match:
            session_ids.add(match.group(1))
        # Derive project root from task file's location ({project}/tasks/task-*.md)
        if tf.parent.name == "tasks":
            project_roots.add(tf.parent.parent)

    if not session_ids:
        return []

    # Search in project-relative log dirs first
    log_files = []
    seen: set = set()

    for project_root in project_roots:
        log_dir = project_root / ".claude" / "logs"
        if not log_dir.exists():
            continue
        for log_file in sorted(log_dir.glob("*.log")):
            key = str(log_file.resolve())
            if key in seen:
                continue
            for sid in session_ids:
                if sid in log_file.name:
                    seen.add(key)
                    log_files.append(log_file)
                    break

    # Fallback to searching across all watch dirs
    if not log_files:
        return find_log_files_for_sessions(list(session_ids), config_path)

    return log_files


def get_summaries_dir(files: List[Path], config_path: Path) -> Path:
    """Get summaries directory derived from task file location.

    If files live in {project}/tasks/, returns {project}/summaries/.
    Otherwise falls back to config's output.summaries_directory.

    Args:
        files: List of task file Paths
        config_path: Path to configuration file

    Returns:
        Path to summaries directory
    """
    if files:
        parent = files[0].parent
        if parent.name == "tasks":
            return parent.parent / "summaries"

    config = Config(config_path) if config_path.exists() else Config(None)
    return Path(config.get("output.summaries_directory", "./summaries"))


def select_daily(date_groups: Dict[date, List[Path]], available_dates: List[date]) -> Tuple[Optional[List[Path]], Optional[str]]:
    """Select a specific date for daily summary.

    Args:
        date_groups: Files grouped by date
        available_dates: Sorted list of available dates

    Returns:
        Tuple of (list of files, range label string) or (None, None)
    """
    choices = []
    for d in sorted(available_dates, reverse=True):
        files = date_groups[d]
        weekday_name = d.strftime("%A")
        total_size = sum(f.stat().st_size for f in files)
        choices.append((
            f"{d.isoformat()} ({weekday_name}) - {len(files)}개 파일, {format_size(total_size)}",
            d.isoformat()
        ))
    choices.append(("Cancel - 취소", "cancel"))

    questions = [
        inquirer.List(
            "date",
            message="요약할 날짜를 선택하세요",
            choices=choices,
        )
    ]
    answers = inquirer.prompt(questions)
    if not answers or answers["date"] == "cancel":
        return None, None

    selected_date = date.fromisoformat(answers["date"])
    files = date_groups[selected_date]
    range_label = f"daily-{selected_date.isoformat()}"
    return files, range_label


def select_weekly(date_groups: Dict[date, List[Path]], available_dates: List[date], config_path: Path) -> Tuple[Optional[List[Path]], Optional[str]]:
    """Select a week for weekly summary.

    Args:
        date_groups: Files grouped by date
        available_dates: Sorted list of available dates
        config_path: Path to configuration file

    Returns:
        Tuple of (list of files, range label string) or (None, None)
    """
    config = Config(config_path) if config_path.exists() else Config(None)
    weekly_start = config.get("summarization.weekly_start", "monday")

    # Monday=0, Sunday=6
    start_weekday = 6 if weekly_start.lower() == "sunday" else 0

    # Build week ranges
    week_ranges = {}
    for d in available_dates:
        days_since_start = (d.weekday() - start_weekday) % 7
        week_start = d - timedelta(days=days_since_start)
        week_end = week_start + timedelta(days=6)

        key = (week_start, week_end)
        if key not in week_ranges:
            week_ranges[key] = []
        week_ranges[key].extend(date_groups[d])

    # Present choices
    choices = []
    for (ws, we) in sorted(week_ranges.keys(), reverse=True):
        files = week_ranges[(ws, we)]
        unique_dates = len(set(
            extract_date_from_filename(f.name) for f in files
            if extract_date_from_filename(f.name)
        ))
        total_size = sum(f.stat().st_size for f in files)
        choices.append((
            f"{ws.isoformat()} ~ {we.isoformat()} ({len(files)}개 파일, {unique_dates}일, {format_size(total_size)})",
            f"{ws.isoformat()}|{we.isoformat()}"
        ))
    choices.append(("Cancel - 취소", "cancel"))

    questions = [
        inquirer.List(
            "week",
            message=f"요약할 주간을 선택하세요 (주 시작: {weekly_start})",
            choices=choices,
        )
    ]
    answers = inquirer.prompt(questions)
    if not answers or answers["week"] == "cancel":
        return None, None

    ws_str, we_str = answers["week"].split("|")
    ws = date.fromisoformat(ws_str)
    we = date.fromisoformat(we_str)

    files = week_ranges[(ws, we)]
    range_label = f"weekly-{ws.isoformat()}_to_{we.isoformat()}"
    return files, range_label


def select_custom_range(date_groups: Dict[date, List[Path]], available_dates: List[date]) -> Tuple[Optional[List[Path]], Optional[str]]:
    """Select custom date range.

    Args:
        date_groups: Files grouped by date
        available_dates: Sorted list of available dates

    Returns:
        Tuple of (list of files, range label string) or (None, None)
    """
    out.print(f"\n   사용 가능한 범위: {available_dates[0].isoformat()} ~ {available_dates[-1].isoformat()}\n")

    try:
        start_input = input("   시작 날짜 (YYYY-MM-DD): ").strip()
        end_input = input("   종료 날짜 (YYYY-MM-DD): ").strip()

        start_date = date.fromisoformat(start_input)
        end_date = date.fromisoformat(end_input)
    except (ValueError, KeyboardInterrupt):
        out.print("\n--- 잘못된 날짜 형식이거나 취소되었습니다.\n")
        return None, None

    if start_date > end_date:
        out.print("\n--- 시작 날짜가 종료 날짜보다 늦습니다.\n")
        return None, None

    files = []
    for d in available_dates:
        if start_date <= d <= end_date:
            files.extend(date_groups[d])

    if not files:
        out.print(f"\n--- {start_date.isoformat()} ~ {end_date.isoformat()} 범위에 파일이 없습니다.\n")
        return None, None

    range_label = f"custom-{start_date.isoformat()}_to_{end_date.isoformat()}"
    return files, range_label
