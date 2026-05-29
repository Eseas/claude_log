"""Interactive CLI entry point for Claude Log Organizer."""

import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import inquirer

from claude_log_organizer.main import LogOrganizerApp
from claude_log_organizer.config import Config
from claude_log_organizer.output import out

from claude_log_organizer.interactive.file_discovery import (
    discover_project_task_files,
    format_size,
    group_files_by_session,
    find_log_files_for_sessions,
    get_summaries_dir,
)
from claude_log_organizer.interactive.handlers import (
    watch_from_config,
    watch_from_manual_input,
    select_analysis_type,
    select_ai_method,
    select_grouping_mode,
    get_api_key,
)
from claude_log_organizer.interactive.analysis import (
    request_ai_summary_by_session,
    request_ai_summary_with_claude_code,
    request_efficiency_analysis_with_claude_code,
    request_efficiency_analysis_with_api,
    handle_date_based_summary,
    generate_timeline_diagram,
    generate_token_analysis,
    generate_task_success_analysis,
)


class InteractiveCLI:
    """Interactive command-line interface."""

    def __init__(self, config_path: Optional[Path] = None):
        """Initialize interactive CLI.

        Args:
            config_path: Path to configuration file
        """
        if config_path and config_path.exists():
            self.config_path = config_path
        else:
            self.config_path = Path("config.yaml")

        self.app = None
        if self.config_path.exists():
            self.app = LogOrganizerApp(self.config_path)

    def run(self):
        """Run interactive CLI."""
        out.print("\n" + "=" * 60)
        out.print("Claude Log Organizer - Interactive Mode")
        out.print("=" * 60 + "\n")

        while True:
            choice = self.show_main_menu()

            if choice == "watch":
                self.handle_watch_menu()
            elif choice == "request_ai":
                self.handle_ai_request_menu()
            elif choice == "exit":
                out.print("\n👋 종료합니다.")
                sys.exit(0)

    def show_main_menu(self) -> str:
        """Show main menu and get user choice.

        Returns:
            Selected option key
        """
        questions = [
            inquirer.List(
                "action",
                message="작업을 선택하세요",
                choices=[
                    ("1. Watch - 디렉토리 모니터링 시작", "watch"),
                    ("2. Request AI - AI 요약 요청", "request_ai"),
                    ("3. Exit - 종료", "exit"),
                ],
            )
        ]

        answers = inquirer.prompt(questions)
        if not answers:
            sys.exit(0)

        return answers["action"]

    def handle_watch_menu(self):
        """Handle watch mode menu."""
        questions = [
            inquirer.List(
                "source",
                message="디렉토리 선택 방법",
                choices=[
                    ("1. Config - 설정 파일의 디렉토리 사용", "config"),
                    ("2. Manual - 직접 입력", "manual"),
                    ("3. Back - 메인 메뉴로 돌아가기", "back"),
                ],
            )
        ]

        answers = inquirer.prompt(questions)
        if not answers or answers["source"] == "back":
            return

        if answers["source"] == "config":
            watch_from_config(self)
        elif answers["source"] == "manual":
            watch_from_manual_input(self)

    def handle_ai_request_menu(self):
        """Handle AI request menu - Group by session ID or date."""

        # Find all task markdown files from project directories
        task_files = sorted(
            discover_project_task_files(self.config_path),
            key=lambda x: x.stat().st_mtime,
            reverse=True,
        )

        if not task_files:
            out.print("\n❌ task 파일이 없습니다.")
            out.print("   먼저 로그를 처리하세요.\n")
            return

        # Select grouping mode
        grouping_mode = select_grouping_mode()
        if not grouping_mode:
            return

        if grouping_mode == "date":
            handle_date_based_summary(task_files, self.config_path)
            return

        # Session-based grouping (existing logic)
        sessions = group_files_by_session(task_files)

        if not sessions:
            out.print("❌ 세션 정보를 추출할 수 없습니다.\n")
            return

        # Create choices
        choices = [("[ All ] - 모든 세션 선택", "ALL")]
        for session_id, files in sorted(sessions.items(), key=lambda x: max(f.stat().st_mtime for f in x[1]), reverse=True):
            total_size = sum(f.stat().st_size for f in files)
            file_count = len(files)
            latest_time = max(f.stat().st_mtime for f in files)
            time_str = datetime.fromtimestamp(latest_time).strftime("%Y-%m-%d %H:%M")

            choices.append((
                f"[ ] {session_id[:8]}... ({file_count}개 파일, {format_size(total_size)}, {time_str})",
                session_id
            ))
        choices.append(("[ Cancel ] - 취소", "CANCEL"))

        # Ask selection mode first
        mode_questions = [
            inquirer.List(
                "mode",
                message="선택 모드를 선택하세요",
                choices=[
                    ("단일 선택 (Enter로 바로 선택)", "single"),
                    ("다중 선택 (Space로 체크 후 Enter)", "multiple"),
                    ("취소", "cancel"),
                ],
            )
        ]

        mode_answer = inquirer.prompt(mode_questions)
        if not mode_answer or mode_answer["mode"] == "cancel":
            out.print("\n취소되었습니다.\n")
            return

        # Single or multiple selection
        if mode_answer["mode"] == "single":
            # Use List for single selection
            questions = [
                inquirer.List(
                    "session",
                    message="AI 요약을 요청할 세션을 선택하세요 (Enter로 선택)",
                    choices=choices,
                )
            ]

            answers = inquirer.prompt(questions)
            if not answers or answers["session"] == "CANCEL":
                out.print("\n취소되었습니다.\n")
                return

            selected_session = answers["session"]
            if selected_session == "ALL":
                selected_sessions = list(sessions.keys())
            else:
                selected_sessions = [selected_session]

        else:
            # Use Checkbox for multiple selection
            questions = [
                inquirer.Checkbox(
                    "sessions",
                    message="AI 요약을 요청할 세션을 선택하세요 (Space로 선택, Enter로 확인)",
                    choices=choices,
                )
            ]

            answers = inquirer.prompt(questions)
            if not answers or not answers["sessions"]:
                out.print("\n취소되었습니다.\n")
                return

            selected_sessions = answers["sessions"]

            # Handle ALL selection
            if "ALL" in selected_sessions:
                selected_sessions = list(sessions.keys())
            else:
                # Remove CANCEL if present
                selected_sessions = [s for s in selected_sessions if s != "CANCEL"]

            if not selected_sessions:
                out.print("\n취소되었습니다.\n")
                return

        # Confirm selection
        total_files = sum(len(sessions[sid]) for sid in selected_sessions)
        out.print(f"\n✓ {len(selected_sessions)}개 세션 선택됨 (총 {total_files}개 파일)")

        # Ask for analysis type
        analysis_type = select_analysis_type()
        if not analysis_type:
            return

        # Timeline diagram doesn't need AI
        if analysis_type == "timeline":
            all_files = []
            for sid in selected_sessions:
                all_files.extend(sessions[sid])
            range_label = f"session-{selected_sessions[0][:8]}" if len(selected_sessions) == 1 else f"sessions-{len(selected_sessions)}"
            generate_timeline_diagram(all_files, range_label, self.config_path)
            return

        # Token analysis doesn't need AI
        if analysis_type == "token_analysis":
            all_files = []
            for sid in selected_sessions:
                all_files.extend(sessions[sid])
            range_label = f"session-{selected_sessions[0][:8]}" if len(selected_sessions) == 1 else f"sessions-{len(selected_sessions)}"
            generate_token_analysis(all_files, range_label, self.config_path)
            return

        # Task success analysis (heuristic always, AI optional)
        if analysis_type == "task_success":
            # Collect log files for selected sessions
            log_files = find_log_files_for_sessions(selected_sessions, self.config_path)
            range_label = f"session-{selected_sessions[0][:8]}" if len(selected_sessions) == 1 else f"sessions-{len(selected_sessions)}"
            generate_task_success_analysis(log_files, range_label, self.config_path)
            return

        # Ask for AI method
        ai_method = select_ai_method()
        if not ai_method:
            return

        # Process sessions with AI
        if analysis_type == "efficiency":
            # Efficiency analysis
            if ai_method == "claude_code":
                request_efficiency_analysis_with_claude_code(sessions, selected_sessions, self.config_path)
            else:
                api_key = get_api_key(self.config_path)
                if not api_key:
                    return
                request_efficiency_analysis_with_api(sessions, selected_sessions, api_key, self.config_path)
        else:
            # Regular summary
            if ai_method == "claude_code":
                request_ai_summary_with_claude_code(sessions, selected_sessions, self.config_path)
            else:
                api_key = get_api_key(self.config_path)
                if not api_key:
                    return
                request_ai_summary_by_session(sessions, selected_sessions, api_key, self.config_path)


def main():
    """Entry point for interactive mode."""
    import argparse

    parser = argparse.ArgumentParser(description="Claude Log Organizer - Interactive Mode")
    parser.add_argument(
        "-c", "--config",
        type=Path,
        default=Path("config.yaml"),
        help="Config file path"
    )

    args = parser.parse_args()

    cli = InteractiveCLI(args.config)
    cli.run()


if __name__ == "__main__":
    main()
