"""Command-line interface for claude-log-organizer."""

import argparse
import sys
from pathlib import Path

from claude_log_organizer.main import LogOrganizerApp
from claude_log_organizer.config import Config
from claude_log_organizer.output import out


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Claude Conversation Log Organizer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create default config
  claude-log-organizer init

  # Watch directory for new logs
  claude-log-organizer watch

  # Process single file
  claude-log-organizer process logs/conversation-task-abc123.log

  # Process entire directory
  claude-log-organizer batch ./logs

  # Clear processed file history
  claude-log-organizer clear

  # Generate timeline diagram for a specific date
  claude-log-organizer timeline 2026-02-19

For more information: https://github.com/yourusername/claude-log-organizer
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # init command
    init_parser = subparsers.add_parser(
        "init", help="Create default configuration file"
    )
    init_parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("config.yaml"),
        help="Config file path (default: config.yaml)",
    )

    # watch command
    watch_parser = subparsers.add_parser(
        "watch", help="Watch directory for new log files"
    )
    watch_parser.add_argument(
        "-c",
        "--config",
        type=Path,
        default=Path("config.yaml"),
        help="Config file path (default: config.yaml)",
    )

    # process command
    process_parser = subparsers.add_parser("process", help="Process single log file")
    process_parser.add_argument("file", type=Path, help="Log file to process")
    process_parser.add_argument(
        "-c",
        "--config",
        type=Path,
        default=Path("config.yaml"),
        help="Config file path (default: config.yaml)",
    )

    # batch command
    batch_parser = subparsers.add_parser(
        "batch", help="Process all logs in directory"
    )
    batch_parser.add_argument("directory", type=Path, help="Directory to process")
    batch_parser.add_argument(
        "-c",
        "--config",
        type=Path,
        default=Path("config.yaml"),
        help="Config file path (default: config.yaml)",
    )
    batch_parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Force reprocess all files, even if already processed",
    )

    # clear command
    clear_parser = subparsers.add_parser("clear", help="Clear processed file history")
    clear_parser.add_argument(
        "-c",
        "--config",
        type=Path,
        default=Path("config.yaml"),
        help="Config file path (default: config.yaml)",
    )

    # timeline command
    timeline_parser = subparsers.add_parser(
        "timeline", help="Generate timeline diagram (.drawio) for a date"
    )
    timeline_parser.add_argument(
        "date", type=str, help="Date in YYYY-MM-DD format"
    )
    timeline_parser.add_argument(
        "-c",
        "--config",
        type=Path,
        default=Path("config.yaml"),
        help="Config file path (default: config.yaml)",
    )

    args = parser.parse_args()

    # If no command specified, launch interactive mode
    if not args.command:
        from claude_log_organizer.interactive import InteractiveCLI
        cli = InteractiveCLI()
        cli.run()
        return

    # Handle commands
    try:
        if args.command == "init":
            handle_init(args)
        elif args.command == "watch":
            handle_watch(args)
        elif args.command == "process":
            handle_process(args)
        elif args.command == "batch":
            handle_batch(args)
        elif args.command == "clear":
            handle_clear(args)
        elif args.command == "timeline":
            handle_timeline(args)
    except KeyboardInterrupt:
        out.print("\nInterrupted by user")
        sys.exit(0)
    except Exception as e:
        out.print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def handle_init(args):
    """Handle init command.

    Args:
        args: Parsed command-line arguments
    """
    output_path = args.output

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


def handle_watch(args):
    """Handle watch command.

    Args:
        args: Parsed command-line arguments
    """
    config_path = args.config if args.config.exists() else None

    if config_path is None:
        out.print("Warning: Config file not found, using default settings")
        out.print(f"Run 'claude-log-organizer init' to create {args.config}")
        out.print()

    app = LogOrganizerApp(config_path)
    app.watch()


def handle_process(args):
    """Handle process command.

    Args:
        args: Parsed command-line arguments
    """
    file_path = args.file
    config_path = args.config if args.config.exists() else None

    if not file_path.exists():
        out.print(f"Error: File not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    app = LogOrganizerApp(config_path)
    app.process_file(file_path)


def handle_batch(args):
    """Handle batch command.

    Args:
        args: Parsed command-line arguments
    """
    directory = args.directory
    config_path = args.config if args.config.exists() else None
    force = args.force

    if not directory.exists():
        out.print(f"Error: Directory not found: {directory}", file=sys.stderr)
        sys.exit(1)

    if not directory.is_dir():
        out.print(f"Error: Not a directory: {directory}", file=sys.stderr)
        sys.exit(1)

    app = LogOrganizerApp(config_path)
    app.process_directory(directory, force=force)


def handle_clear(args):
    """Handle clear command.

    Args:
        args: Parsed command-line arguments
    """
    config_path = args.config if args.config.exists() else None

    response = input("Clear processed file history? This cannot be undone. [y/N]: ")
    if response.lower() != "y":
        out.print("Cancelled")
        return

    from claude_log_organizer.config import Config
    from claude_log_organizer.storage.processed_tracker import ProcessedTracker

    config = Config(config_path)
    tracker = ProcessedTracker(Path(config.get("storage.processed_log")))
    tracker.clear()

    out.print("✓ Cleared processed file history")


def handle_timeline(args):
    """Handle timeline command.

    Args:
        args: Parsed command-line arguments
    """
    from datetime import date as dt_date
    from claude_log_organizer.generators.timeline import TimelineDiagramGenerator

    try:
        target_date = dt_date.fromisoformat(args.date)
    except ValueError:
        out.print(f"Error: Invalid date format: {args.date} (expected YYYY-MM-DD)", file=sys.stderr)
        sys.exit(1)

    config_path = args.config if args.config.exists() else None
    config = Config(config_path)

    # Search for task files across all project directories from watch config
    watch_dirs = config.get("watch.directories", [])
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
        for f in sorted((project_root / "tasks").glob(f"task-{args.date}_*.md")):
            key = str(f.resolve())
            if key not in seen:
                seen.add(key)
                task_files.append(f)

    # Fallback to config output.directory
    if not task_files:
        output_dir = Path(config.get("output.directory", "./tasks"))
        task_files = sorted(output_dir.glob(f"task-{args.date}_*.md"))

    if not task_files:
        out.print(f"No task files found for {args.date}")
        sys.exit(1)

    out.print(f"Found {len(task_files)} task files for {args.date}")

    generator = TimelineDiagramGenerator()
    # Derive summaries dir from first task file's project root
    first = task_files[0]
    if first.parent.name == "tasks":
        summaries_dir = first.parent.parent / "summaries"
    else:
        summaries_dir = Path(config.get("output.summaries_directory", "./summaries"))
    summaries_dir.mkdir(parents=True, exist_ok=True)
    output_path = summaries_dir / f"daily-{args.date}_timeline.drawio"

    generator.generate(task_files, f"daily-{args.date}", output_path)
    out.print(f"✓ Timeline saved: {output_path}")


if __name__ == "__main__":
    main()
