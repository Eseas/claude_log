"""Command-line interface for claude-log-organizer (Typer-based)."""

import sys
from pathlib import Path

import typer

from claude_log_organizer.main import LogOrganizerApp
from claude_log_organizer.config import Config
from claude_log_organizer.output import out

CONFIG_OPTION = typer.Option(
    Path("config.yaml"), "-c", "--config", help="Config file path (default: config.yaml)"
)

app = typer.Typer(
    add_completion=False,
    no_args_is_help=False,
    help="Claude Conversation Log Organizer — organize Claude session logs into markdown.",
)


@app.callback(invoke_without_command=True)
def _entry(ctx: typer.Context) -> None:
    """Run with no command to launch interactive mode."""
    if ctx.invoked_subcommand is None:
        from claude_log_organizer.interactive import InteractiveCLI
        InteractiveCLI().run()


@app.command()
def init(
    output: Path = typer.Option(
        Path("config.yaml"), "-o", "--output", help="Config file path (default: config.yaml)"
    ),
) -> None:
    """Create a default configuration file."""
    handle_init(output)


@app.command()
def watch(config: Path = CONFIG_OPTION) -> None:
    """Watch directories for new log files and process them."""
    handle_watch(config)


@app.command()
def process(
    file: Path = typer.Argument(..., help="Log file to process"),
    config: Path = CONFIG_OPTION,
) -> None:
    """Process a single log file."""
    handle_process(file, config)


@app.command()
def batch(
    directory: Path = typer.Argument(..., help="Directory to process"),
    config: Path = CONFIG_OPTION,
    force: bool = typer.Option(
        False, "-f", "--force", help="Force reprocess all files, even if already processed"
    ),
) -> None:
    """Process all logs in a directory."""
    handle_batch(directory, config, force)


@app.command()
def clear(config: Path = CONFIG_OPTION) -> None:
    """Clear the processed-file history."""
    handle_clear(config)


@app.command()
def timeline(
    date: str = typer.Argument(..., help="Date in YYYY-MM-DD format"),
    config: Path = CONFIG_OPTION,
) -> None:
    """Generate a timeline diagram (.drawio) for a date."""
    handle_timeline(date, config)


def main():
    """CLI entry point with top-level interrupt/error handling."""
    try:
        app()
    except KeyboardInterrupt:
        out.print("\nInterrupted by user")
        sys.exit(0)
    except SystemExit:
        raise
    except Exception as e:
        out.print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def handle_init(output_path: Path) -> None:
    """Create the default config, prompting before overwrite."""
    if output_path.exists():
        response = input(f"{output_path} already exists. Overwrite? [y/N]: ")
        if response.lower() != "y":
            out.print("Cancelled")
            return

    Config.create_default(output_path)
    out.print(f"✓ Created config file: {output_path}")
    out.print("\nNext steps:")
    out.print("1. Edit config.yaml to customize settings")
    out.print("2. Run 'claude-log-organizer watch' to start monitoring")


def handle_watch(config: Path) -> None:
    """Start the file watcher."""
    config_path = config if config.exists() else None

    if config_path is None:
        out.print("Warning: Config file not found, using default settings")
        out.print(f"Run 'claude-log-organizer init' to create {config}")
        out.print()

    app_instance = LogOrganizerApp(config_path)
    app_instance.watch()


def handle_process(file_path: Path, config: Path) -> None:
    """Process a single log file."""
    config_path = config if config.exists() else None

    if not file_path.exists():
        out.print(f"Error: File not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    app_instance = LogOrganizerApp(config_path)
    app_instance.process_file(file_path)


def handle_batch(directory: Path, config: Path, force: bool) -> None:
    """Process all log files in a directory."""
    config_path = config if config.exists() else None

    if not directory.exists():
        out.print(f"Error: Directory not found: {directory}", file=sys.stderr)
        sys.exit(1)

    if not directory.is_dir():
        out.print(f"Error: Not a directory: {directory}", file=sys.stderr)
        sys.exit(1)

    app_instance = LogOrganizerApp(config_path)
    app_instance.process_directory(directory, force=force)


def handle_clear(config: Path) -> None:
    """Clear the processed-file history after confirmation."""
    config_path = config if config.exists() else None

    response = input("Clear processed file history? This cannot be undone. [y/N]: ")
    if response.lower() != "y":
        out.print("Cancelled")
        return

    from claude_log_organizer.storage.processed_tracker import ProcessedTracker

    cfg = Config(config_path)
    tracker = ProcessedTracker(Path(cfg.get("storage.processed_log")))
    tracker.clear()

    out.print("✓ Cleared processed file history")


def handle_timeline(date: str, config: Path) -> None:
    """Generate a timeline diagram for the given date."""
    from datetime import date as dt_date
    from claude_log_organizer.generators.timeline import TimelineDiagramGenerator

    try:
        dt_date.fromisoformat(date)
    except ValueError:
        out.print(f"Error: Invalid date format: {date} (expected YYYY-MM-DD)", file=sys.stderr)
        sys.exit(1)

    config_path = config if config.exists() else None
    cfg = Config(config_path)

    # Search for task files across all project directories from watch config
    watch_dirs = cfg.get("watch.directories", [])
    if isinstance(watch_dirs, str):
        watch_dirs = [watch_dirs]

    task_files = []
    seen: set = set()
    for wd_str in watch_dirs:
        wd = Path(wd_str).expanduser()
        if wd.name == "logs" and wd.parent.name == ".claude":
            project_root = wd.parent.parent
        else:
            project_root = wd.parent
        for f in sorted((project_root / "tasks").glob(f"task-{date}_*.md")):
            key = str(f.resolve())
            if key not in seen:
                seen.add(key)
                task_files.append(f)

    # Fallback to config output.directory
    if not task_files:
        output_dir = Path(cfg.get("output.directory", "./tasks"))
        task_files = sorted(output_dir.glob(f"task-{date}_*.md"))

    if not task_files:
        out.print(f"No task files found for {date}")
        sys.exit(1)

    out.print(f"Found {len(task_files)} task files for {date}")

    generator = TimelineDiagramGenerator()
    first = task_files[0]
    if first.parent.name == "tasks":
        summaries_dir = first.parent.parent / "summaries"
    else:
        summaries_dir = Path(cfg.get("output.summaries_directory", "./summaries"))
    summaries_dir.mkdir(parents=True, exist_ok=True)
    output_path = summaries_dir / f"daily-{date}_timeline.drawio"

    generator.generate(task_files, f"daily-{date}", output_path)
    out.print(f"✓ Timeline saved: {output_path}")


if __name__ == "__main__":
    main()
