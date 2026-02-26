"""Interactive CLI for Claude Log Organizer."""

import re
import sys
from datetime import date, datetime, timedelta
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import inquirer
from inquirer import errors

from claude_log_organizer.main import LogOrganizerApp
from claude_log_organizer.config import Config


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
        print("\n" + "=" * 60)
        print("Claude Log Organizer - Interactive Mode")
        print("=" * 60 + "\n")

        while True:
            choice = self.show_main_menu()

            if choice == "watch":
                self.handle_watch_menu()
            elif choice == "request_ai":
                self.handle_ai_request_menu()
            elif choice == "exit":
                print("\n👋 종료합니다.")
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
            self.watch_from_config()
        elif answers["source"] == "manual":
            self.watch_from_manual_input()

    def watch_from_config(self):
        """Start watching using directories from config."""
        if not self.config_path.exists():
            print("\n❌ 설정 파일이 없습니다. 먼저 'init' 명령으로 생성하세요.")
            return

        if not self.app:
            self.app = LogOrganizerApp(self.config_path)

        config = Config(self.config_path)
        directories = config.get("watch.directories", ["./logs"])

        if isinstance(directories, str):
            directories = [directories]

        print("\n📂 설정된 디렉토리:")
        for i, d in enumerate(directories, 1):
            print(f"  {i}. {Path(d).absolute()}")

        print("\n⏳ 모니터링을 시작합니다...")
        print("   (Ctrl+C를 눌러 중지)\n")

        try:
            self.app.watch()
        except KeyboardInterrupt:
            print("\n\n✓ 모니터링을 중지했습니다.\n")

    def watch_from_manual_input(self):
        """Start watching using manually input directories."""
        directories = []

        print("\n📝 모니터링할 디렉토리를 입력하세요")
        print("   (빈 값을 입력하면 완료)\n")

        while True:
            try:
                path = input(f"디렉토리 {len(directories) + 1}: ").strip()

                if not path:
                    if not directories:
                        print("❌ 최소 1개 이상의 디렉토리를 입력해야 합니다.")
                        continue
                    break

                path_obj = Path(path).expanduser().absolute()

                if not path_obj.exists():
                    create = input(f"⚠️  '{path_obj}'가 존재하지 않습니다. 생성하시겠습니까? (y/N): ")
                    if create.lower() == 'y':
                        path_obj.mkdir(parents=True, exist_ok=True)
                        print(f"✓ 디렉토리 생성됨: {path_obj}")
                    else:
                        continue

                directories.append(str(path_obj))
                print(f"✓ 추가됨: {path_obj}")

            except KeyboardInterrupt:
                print("\n\n취소되었습니다.\n")
                return

        if not directories:
            return

        # Create temporary config
        print("\n📂 선택된 디렉토리:")
        for i, d in enumerate(directories, 1):
            print(f"  {i}. {d}")

        # Update app config temporarily
        if not self.app:
            self.app = LogOrganizerApp(self.config_path if self.config_path.exists() else None)

        # Temporarily override watch directories
        self.app.config.data["watch"]["directories"] = directories

        print("\n⏳ 모니터링을 시작합니다...")
        print("   (Ctrl+C를 눌러 중지)\n")

        # Recreate watcher with new config
        from claude_log_organizer.watcher.file_watcher import ConversationLogWatcher
        self.app.watcher = ConversationLogWatcher(self.app.config)

        try:
            self.app.watcher.start(callback=self.app.dispatcher.dispatch_file_event)
        except KeyboardInterrupt:
            print("\n\n✓ 모니터링을 중지했습니다.\n")

    def handle_ai_request_menu(self):
        """Handle AI request menu - Group by session ID or date."""

        # Get output directory from config
        config = Config(self.config_path) if self.config_path.exists() else Config(None)
        output_dir = Path(config.get("output.directory", "./tasks"))

        if not output_dir.exists():
            print(f"\n❌ 출력 디렉토리가 없습니다: {output_dir}")
            print("   먼저 로그를 처리하세요.\n")
            return

        # Find all task markdown files
        task_files = sorted(output_dir.glob("task-*.md"), key=lambda x: x.stat().st_mtime, reverse=True)

        if not task_files:
            print(f"\n❌ {output_dir}에 task 파일이 없습니다.")
            print("   먼저 로그를 처리하세요.\n")
            return

        # Select grouping mode
        grouping_mode = self._select_grouping_mode()
        if not grouping_mode:
            return

        if grouping_mode == "date":
            self._handle_date_based_summary(task_files)
            return

        # Session-based grouping (existing logic)
        sessions = self._group_files_by_session(task_files)

        if not sessions:
            print("❌ 세션 정보를 추출할 수 없습니다.\n")
            return

        # Create choices
        choices = [("[ All ] - 모든 세션 선택", "ALL")]
        for session_id, files in sorted(sessions.items(), key=lambda x: max(f.stat().st_mtime for f in x[1]), reverse=True):
            total_size = sum(f.stat().st_size for f in files)
            file_count = len(files)
            latest_time = max(f.stat().st_mtime for f in files)
            time_str = datetime.fromtimestamp(latest_time).strftime("%Y-%m-%d %H:%M")

            choices.append((
                f"[ ] {session_id[:8]}... ({file_count}개 파일, {self._format_size(total_size)}, {time_str})",
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
            print("\n취소되었습니다.\n")
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
                print("\n취소되었습니다.\n")
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
                print("\n취소되었습니다.\n")
                return

            selected_sessions = answers["sessions"]

            # Handle ALL selection
            if "ALL" in selected_sessions:
                selected_sessions = list(sessions.keys())
            else:
                # Remove CANCEL if present
                selected_sessions = [s for s in selected_sessions if s != "CANCEL"]

            if not selected_sessions:
                print("\n취소되었습니다.\n")
                return

        # Confirm selection
        total_files = sum(len(sessions[sid]) for sid in selected_sessions)
        print(f"\n✓ {len(selected_sessions)}개 세션 선택됨 (총 {total_files}개 파일)")

        # Ask for analysis type
        analysis_type = self._select_analysis_type()
        if not analysis_type:
            return

        # Ask for AI method
        ai_method = self._select_ai_method()
        if not ai_method:
            return

        # Process sessions with AI
        if analysis_type == "efficiency":
            # Efficiency analysis
            if ai_method == "claude_code":
                self._request_efficiency_analysis_with_claude_code(sessions, selected_sessions)
            else:
                api_key = self._get_api_key(config)
                if not api_key:
                    return
                self._request_efficiency_analysis_with_api(sessions, selected_sessions, api_key)
        else:
            # Regular summary
            if ai_method == "claude_code":
                self._request_ai_summary_with_claude_code(sessions, selected_sessions)
            else:
                api_key = self._get_api_key(config)
                if not api_key:
                    return
                self._request_ai_summary_by_session(sessions, selected_sessions, api_key)

    def _group_files_by_session(self, task_files: List[Path]) -> dict:
        """Group task files by session ID.

        Args:
            task_files: List of task markdown files

        Returns:
            Dictionary mapping session ID to list of files
        """
        import re

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

    def _extract_date_from_filename(self, filename: str) -> Optional[date]:
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

    def _group_files_by_date(self, task_files: List[Path]) -> Dict[date, List[Path]]:
        """Group task files by date extracted from filename.

        Args:
            task_files: List of task markdown files

        Returns:
            Dictionary mapping date to list of files, sorted by date
        """
        date_groups = defaultdict(list)
        for f in task_files:
            file_date = self._extract_date_from_filename(f.name)
            if file_date:
                date_groups[file_date].append(f)

        for d in date_groups:
            date_groups[d].sort(key=lambda x: x.name)

        return dict(sorted(date_groups.items()))

    def _select_analysis_type(self) -> Optional[str]:
        """Select analysis type.

        Returns:
            'summary' or 'efficiency' or None if cancelled
        """
        questions = [
            inquirer.List(
                "type",
                message="분석 타입을 선택하세요",
                choices=[
                    ("일반 요약 - 세션 작업 내용 요약", "summary"),
                    ("효율성 분석 - 프롬프트 효율성 + 개선 제안", "efficiency"),
                    ("취소", "cancel"),
                ],
            )
        ]

        answers = inquirer.prompt(questions)
        if not answers or answers["type"] == "cancel":
            return None

        return answers["type"]

    def _select_ai_method(self) -> Optional[str]:
        """Select AI method (Claude Code CLI or API).

        Returns:
            'claude_code' or 'api' or None if cancelled
        """
        import shutil

        # Check if Claude CLI is available
        claude_available = shutil.which("claude") is not None

        if not claude_available:
            print("\n⚠️  Claude Code CLI를 찾을 수 없습니다.")
            print("   API 키 방식만 사용 가능합니다.\n")
            return "api"

        questions = [
            inquirer.List(
                "method",
                message="AI 요약 방식을 선택하세요",
                choices=[
                    ("Claude Code CLI 사용 (추천)", "claude_code"),
                    ("API 키 사용", "api"),
                    ("취소", "cancel"),
                ],
            )
        ]

        answers = inquirer.prompt(questions)
        if not answers or answers["method"] == "cancel":
            return None

        return answers["method"]

    def _format_size(self, size_bytes: int) -> str:
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

    def _get_api_key(self, config: Config) -> Optional[str]:
        """Get API key from config or user input.

        Args:
            config: Configuration object

        Returns:
            API key or None if cancelled
        """
        # Try to get from config
        api_key = config.get("ai.api_key")

        if not api_key:
            print("\n🔑 Claude API 키가 필요합니다.")
            print("   https://console.anthropic.com/account/keys 에서 발급받으세요.\n")

            api_key = input("API Key: ").strip()

            if not api_key:
                print("\n❌ API 키가 입력되지 않았습니다.\n")
                return None

            # Ask to save
            save = input("\n이 API 키를 config.yaml에 저장하시겠습니까? (y/N): ")
            if save.lower() == 'y':
                config.data.setdefault("ai", {})["api_key"] = api_key
                # Save config
                import yaml
                with open(self.config_path, 'w') as f:
                    yaml.dump(config.data, f, default_flow_style=False, allow_unicode=True)
                print("✓ 저장되었습니다.")

        return api_key

    def _request_ai_summary_by_session(self, sessions: dict, selected_sessions: List[str], api_key: str):
        """Request AI summary for selected sessions.

        Args:
            sessions: Dictionary mapping session ID to list of files
            selected_sessions: List of session IDs to summarize
            api_key: Claude API key
        """
        try:
            from anthropic import Anthropic
        except ImportError:
            print("\n❌ anthropic 패키지가 설치되지 않았습니다.")
            print("   다음 명령으로 설치하세요: pip install anthropic\n")
            return

        client = Anthropic(api_key=api_key)

        print(f"\n⏳ {len(selected_sessions)}개 세션을 AI로 요약 중...\n")

        for i, session_id in enumerate(selected_sessions, 1):
            files = sessions[session_id]
            print(f"[{i}/{len(selected_sessions)}] Session: {session_id[:8]}... ({len(files)}개 파일)")

            try:
                # Combine all files from this session
                combined_content = []
                combined_content.append(f"# Session: {session_id}\n")
                combined_content.append(f"파일 개수: {len(files)}\n\n")

                for file in sorted(files, key=lambda x: x.stat().st_mtime):
                    combined_content.append(f"\n## 파일: {file.name}\n")
                    content = file.read_text(encoding='utf-8')
                    combined_content.append(content)
                    combined_content.append("\n---\n")

                full_content = "\n".join(combined_content)

                # Request summary
                message = client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=3000,
                    messages=[{
                        "role": "user",
                        "content": f"""다음은 동일한 세션(Session ID: {session_id})에서 진행된 Claude와의 작업 로그를 정리한 마크다운 파일들입니다.

이 세션 전체에서 수행한 작업을 종합적으로 요약해주세요.

포함할 내용:
1. **세션 요약**: 이 세션에서 무슨 일을 했는지 2-3문장으로 요약
2. **주요 작업 흐름**: 작업이 어떻게 진행되었는지 시간 순서대로 간략히 설명
3. **수정/생성된 파일**: 주요 파일 목록과 변경 내용
4. **핵심 기술적 결정사항**: 중요한 기술적 선택이나 해결 방법
5. **결과**: 최종적으로 무엇이 완성되었는지

마크다운 형식으로 작성해주세요.

---

{full_content}
"""
                    }]
                )

                summary = message.content[0].text

                # Save summary with session ID
                config = Config(self.config_path) if self.config_path.exists() else Config(None)
                summaries_dir = Path(config.get("output.summaries_directory", "./summaries"))
                summaries_dir.mkdir(parents=True, exist_ok=True)
                summary_path = summaries_dir / f"session-{session_id[:8]}_summary.md"

                # Create comprehensive summary
                summary_content = [
                    f"# Session 요약: {session_id}\n",
                    f"**파일 개수**: {len(files)}",
                    f"**세션 파일들**:",
                ]
                for f in sorted(files, key=lambda x: x.stat().st_mtime):
                    summary_content.append(f"- [{f.name}]({f.name})")

                summary_content.append("\n---\n")
                summary_content.append(summary)

                summary_path.write_text("\n".join(summary_content), encoding='utf-8')

                print(f"  ✓ 요약 완료: {summary_path.name}")

            except Exception as e:
                print(f"  ❌ 오류: {e}")
                import traceback
                traceback.print_exc()

        print(f"\n✓ 완료! {len(selected_sessions)}개 세션 요약 생성됨\n")

    def _request_ai_summary_with_claude_code(self, sessions: dict, selected_sessions: List[str]):
        """Request AI summary using Claude Code CLI.

        Args:
            sessions: Dictionary mapping session ID to list of files
            selected_sessions: List of session IDs to summarize
        """
        import subprocess
        import tempfile

        print(f"\n⏳ {len(selected_sessions)}개 세션을 Claude Code로 요약 중...\n")

        for i, session_id in enumerate(selected_sessions, 1):
            files = sessions[session_id]
            print(f"[{i}/{len(selected_sessions)}] Session: {session_id[:8]}... ({len(files)}개 파일)")

            try:
                # Combine all files from this session
                combined_content = []
                combined_content.append(f"# Session: {session_id}\n")
                combined_content.append(f"파일 개수: {len(files)}\n\n")

                for file in sorted(files, key=lambda x: x.stat().st_mtime):
                    combined_content.append(f"\n## 파일: {file.name}\n")
                    content = file.read_text(encoding='utf-8')
                    combined_content.append(content)
                    combined_content.append("\n---\n")

                full_content = "\n".join(combined_content)

                # Create prompt
                prompt = f"""다음은 동일한 세션(Session ID: {session_id})에서 진행된 Claude와의 작업 로그를 정리한 마크다운 파일들입니다.

이 세션 전체에서 수행한 작업을 종합적으로 요약해주세요.

포함할 내용:
1. **세션 요약**: 이 세션에서 무슨 일을 했는지 2-3문장으로 요약
2. **주요 작업 흐름**: 작업이 어떻게 진행되었는지 시간 순서대로 간략히 설명
3. **수정/생성된 파일**: 주요 파일 목록과 변경 내용
4. **핵심 기술적 결정사항**: 중요한 기술적 선택이나 해결 방법
5. **결과**: 최종적으로 무엇이 완성되었는지

마크다운 형식으로 작성해주세요.

---

{full_content}
"""

                # Call Claude Code CLI with --print flag
                # Use current project directory for settings.local.json
                project_root = Path(__file__).parent.parent

                result = subprocess.run(
                    [
                        "claude",
                        "--print",
                        "--add-dir", str(project_root / "tasks")
                    ],
                    input=prompt,  # Pass prompt via stdin
                    capture_output=True,
                    text=True,
                    cwd=str(project_root),  # Use project root for settings.local.json
                    timeout=120  # 2 minutes timeout
                )

                if result.returncode != 0:
                    print(f"  ❌ Claude Code 실행 오류: {result.stderr}")
                    continue

                summary = result.stdout.strip()

                # Save summary with session ID
                config = Config(self.config_path) if self.config_path.exists() else Config(None)
                summaries_dir = Path(config.get("output.summaries_directory", "./summaries"))
                summaries_dir.mkdir(parents=True, exist_ok=True)
                summary_path = summaries_dir / f"session-{session_id[:8]}_summary.md"

                # Create comprehensive summary
                summary_content = [
                    f"# Session 요약: {session_id}\n",
                    f"**파일 개수**: {len(files)}",
                    f"**세션 파일들**:",
                ]
                for f in sorted(files, key=lambda x: x.stat().st_mtime):
                    summary_content.append(f"- [{f.name}]({f.name})")

                summary_content.append("\n---\n")
                summary_content.append(summary)

                summary_path.write_text("\n".join(summary_content), encoding='utf-8')

                print(f"  ✓ 요약 완료: {summary_path.name}")

            except subprocess.TimeoutExpired:
                print(f"  ❌ 시간 초과 (2분)")
            except Exception as e:
                print(f"  ❌ 오류: {e}")
                import traceback
                traceback.print_exc()

        print(f"\n✓ 완료! {len(selected_sessions)}개 세션 요약 생성됨\n")

    def _request_efficiency_analysis_with_claude_code(self, sessions: dict, selected_sessions: List[str]):
        """Request efficiency analysis using Claude Code CLI.

        Args:
            sessions: Dictionary mapping session ID to list of files
            selected_sessions: List of session IDs to analyze
        """
        import subprocess
        import sys

        # Add prompt_optimizer to path
        project_root = Path(__file__).parent.parent
        sys.path.insert(0, str(project_root))

        from prompt_optimizer.analyzers import SessionAnalyzer

        analyzer = SessionAnalyzer()

        print(f"\n⏳ {len(selected_sessions)}개 세션을 효율성 분석 중...\n")

        for i, session_id in enumerate(selected_sessions, 1):
            files = sessions[session_id]
            print(f"[{i}/{len(selected_sessions)}] Session: {session_id[:8]}... ({len(files)}개 파일)")

            try:
                # Create analysis prompt using analyzer
                prompt = analyzer.create_analysis_prompt(session_id, files)

                # Call Claude Code CLI
                result = subprocess.run(
                    [
                        "claude",
                        "--print",
                        "--add-dir", str(project_root / "tasks")
                    ],
                    input=prompt,
                    capture_output=True,
                    text=True,
                    cwd=str(project_root),
                    timeout=180  # 3 minutes for analysis
                )

                if result.returncode != 0:
                    print(f"  ❌ Claude Code 실행 오류: {result.stderr}")
                    continue

                analysis = result.stdout.strip()

                # Save efficiency analysis
                config = Config(self.config_path) if self.config_path.exists() else Config(None)
                summaries_dir = Path(config.get("output.summaries_directory", "./summaries"))
                summaries_dir.mkdir(parents=True, exist_ok=True)
                analysis_path = summaries_dir / f"session-{session_id[:8]}_efficiency.md"

                # Create comprehensive analysis
                analysis_content = [
                    f"# Session 효율성 분석: {session_id}\n",
                    f"**파일 개수**: {len(files)}",
                    f"**분석 타입**: 프롬프트 효율성",
                    f"**세션 파일들**:",
                ]
                for f in sorted(files, key=lambda x: x.stat().st_mtime):
                    analysis_content.append(f"- [{f.name}]({f.name})")

                analysis_content.append("\n---\n")
                analysis_content.append(analysis)

                analysis_path.write_text("\n".join(analysis_content), encoding='utf-8')

                print(f"  ✓ 분석 완료: {analysis_path.name}")

            except subprocess.TimeoutExpired:
                print(f"  ❌ 시간 초과 (3분)")
            except Exception as e:
                print(f"  ❌ 오류: {e}")
                import traceback
                traceback.print_exc()

        print(f"\n✓ 완료! {len(selected_sessions)}개 세션 효율성 분석 생성됨\n")

    def _request_efficiency_analysis_with_api(self, sessions: dict, selected_sessions: List[str], api_key: str):
        """Request efficiency analysis using Claude API.

        Args:
            sessions: Dictionary mapping session ID to list of files
            selected_sessions: List of session IDs to analyze
            api_key: Claude API key
        """
        try:
            from anthropic import Anthropic
        except ImportError:
            print("\n❌ anthropic 패키지가 설치되지 않았습니다.")
            print("   다음 명령으로 설치하세요: pip install anthropic\n")
            return

        import sys

        # Add prompt_optimizer to path
        project_root = Path(__file__).parent.parent
        sys.path.insert(0, str(project_root))

        from prompt_optimizer.analyzers import SessionAnalyzer

        analyzer = SessionAnalyzer()
        client = Anthropic(api_key=api_key)

        print(f"\n⏳ {len(selected_sessions)}개 세션을 효율성 분석 중...\n")

        for i, session_id in enumerate(selected_sessions, 1):
            files = sessions[session_id]
            print(f"[{i}/{len(selected_sessions)}] Session: {session_id[:8]}... ({len(files)}개 파일)")

            try:
                # Create analysis prompt using analyzer
                prompt = analyzer.create_analysis_prompt(session_id, files)

                # Request analysis
                message = client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=4000,
                    messages=[{
                        "role": "user",
                        "content": prompt
                    }]
                )

                analysis = message.content[0].text

                # Save efficiency analysis
                config = Config(self.config_path) if self.config_path.exists() else Config(None)
                summaries_dir = Path(config.get("output.summaries_directory", "./summaries"))
                summaries_dir.mkdir(parents=True, exist_ok=True)
                analysis_path = summaries_dir / f"session-{session_id[:8]}_efficiency.md"

                # Create comprehensive analysis
                analysis_content = [
                    f"# Session 효율성 분석: {session_id}\n",
                    f"**파일 개수**: {len(files)}",
                    f"**분석 타입**: 프롬프트 효율성",
                    f"**세션 파일들**:",
                ]
                for f in sorted(files, key=lambda x: x.stat().st_mtime):
                    analysis_content.append(f"- [{f.name}]({f.name})")

                analysis_content.append("\n---\n")
                analysis_content.append(analysis)

                analysis_path.write_text("\n".join(analysis_content), encoding='utf-8')

                print(f"  ✓ 분석 완료: {analysis_path.name}")

            except Exception as e:
                print(f"  ❌ 오류: {e}")
                import traceback
                traceback.print_exc()

        print(f"\n✓ 완료! {len(selected_sessions)}개 세션 효율성 분석 생성됨\n")

    # ===== Date-based summarization methods =====

    def _select_grouping_mode(self) -> Optional[str]:
        """Select grouping mode: session-based or date-based.

        Returns:
            'session', 'date', or None if cancelled
        """
        questions = [
            inquirer.List(
                "mode",
                message="그룹화 방식을 선택하세요",
                choices=[
                    ("1. Session - 세션 ID별 그룹화", "session"),
                    ("2. Date - 날짜 기반 그룹화", "date"),
                    ("3. Back - 돌아가기", "back"),
                ],
            )
        ]
        answers = inquirer.prompt(questions)
        if not answers or answers["mode"] == "back":
            return None
        return answers["mode"]

    def _select_date_mode(self) -> Optional[str]:
        """Select date-based summarization mode.

        Returns:
            'daily', 'weekly', 'custom', or None
        """
        questions = [
            inquirer.List(
                "mode",
                message="날짜 그룹화 방식을 선택하세요",
                choices=[
                    ("1. Daily - 특정 날짜의 모든 작업 요약", "daily"),
                    ("2. Weekly - 주간 단위 요약", "weekly"),
                    ("3. Custom - 날짜 범위 직접 지정", "custom"),
                    ("4. Back - 돌아가기", "back"),
                ],
            )
        ]
        answers = inquirer.prompt(questions)
        if not answers or answers["mode"] == "back":
            return None
        return answers["mode"]

    def _select_daily(self, date_groups: Dict[date, List[Path]], available_dates: List[date]) -> Tuple[Optional[List[Path]], Optional[str]]:
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
                f"{d.isoformat()} ({weekday_name}) - {len(files)}개 파일, {self._format_size(total_size)}",
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

    def _select_weekly(self, date_groups: Dict[date, List[Path]], available_dates: List[date]) -> Tuple[Optional[List[Path]], Optional[str]]:
        """Select a week for weekly summary.

        Args:
            date_groups: Files grouped by date
            available_dates: Sorted list of available dates

        Returns:
            Tuple of (list of files, range label string) or (None, None)
        """
        config = Config(self.config_path) if self.config_path.exists() else Config(None)
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
                self._extract_date_from_filename(f.name) for f in files
                if self._extract_date_from_filename(f.name)
            ))
            total_size = sum(f.stat().st_size for f in files)
            choices.append((
                f"{ws.isoformat()} ~ {we.isoformat()} ({len(files)}개 파일, {unique_dates}일, {self._format_size(total_size)})",
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

    def _select_custom_range(self, date_groups: Dict[date, List[Path]], available_dates: List[date]) -> Tuple[Optional[List[Path]], Optional[str]]:
        """Select custom date range.

        Args:
            date_groups: Files grouped by date
            available_dates: Sorted list of available dates

        Returns:
            Tuple of (list of files, range label string) or (None, None)
        """
        print(f"\n   사용 가능한 범위: {available_dates[0].isoformat()} ~ {available_dates[-1].isoformat()}\n")

        try:
            start_input = input("   시작 날짜 (YYYY-MM-DD): ").strip()
            end_input = input("   종료 날짜 (YYYY-MM-DD): ").strip()

            start_date = date.fromisoformat(start_input)
            end_date = date.fromisoformat(end_input)
        except (ValueError, KeyboardInterrupt):
            print("\n--- 잘못된 날짜 형식이거나 취소되었습니다.\n")
            return None, None

        if start_date > end_date:
            print("\n--- 시작 날짜가 종료 날짜보다 늦습니다.\n")
            return None, None

        files = []
        for d in available_dates:
            if start_date <= d <= end_date:
                files.extend(date_groups[d])

        if not files:
            print(f"\n--- {start_date.isoformat()} ~ {end_date.isoformat()} 범위에 파일이 없습니다.\n")
            return None, None

        range_label = f"custom-{start_date.isoformat()}_to_{end_date.isoformat()}"
        return files, range_label

    def _handle_date_based_summary(self, task_files: List[Path]):
        """Handle date-based summarization flow.

        Args:
            task_files: All task files from the output directory
        """
        date_groups = self._group_files_by_date(task_files)

        if not date_groups:
            print("\n--- 날짜 형식의 task 파일이 없습니다.")
            print("    (task-YYYY-MM-DD_HHMMSS_UUID.md 형식만 지원)\n")
            return

        available_dates = sorted(date_groups.keys())
        print(f"\n--- 사용 가능한 날짜 범위: {available_dates[0]} ~ {available_dates[-1]}")
        print(f"    총 {len(available_dates)}일, {sum(len(v) for v in date_groups.values())}개 파일\n")

        # Select date mode
        date_mode = self._select_date_mode()
        if not date_mode:
            return

        # Get files for selected date range
        if date_mode == "daily":
            selected_files, range_label = self._select_daily(date_groups, available_dates)
        elif date_mode == "weekly":
            selected_files, range_label = self._select_weekly(date_groups, available_dates)
        elif date_mode == "custom":
            selected_files, range_label = self._select_custom_range(date_groups, available_dates)
        else:
            return

        if not selected_files:
            return

        print(f"\n✓ 선택된 파일: {len(selected_files)}개")

        # Reuse existing analysis type + AI method selection
        analysis_type = self._select_analysis_type()
        if not analysis_type:
            return

        ai_method = self._select_ai_method()
        if not ai_method:
            return

        config = Config(self.config_path) if self.config_path.exists() else Config(None)

        if analysis_type == "summary":
            if ai_method == "claude_code":
                self._request_date_summary_with_claude_code(selected_files, range_label)
            else:
                api_key = self._get_api_key(config)
                if not api_key:
                    return
                self._request_date_summary_with_api(selected_files, range_label, api_key)
        else:
            if ai_method == "claude_code":
                self._request_date_summary_with_claude_code(selected_files, range_label)
            else:
                api_key = self._get_api_key(config)
                if not api_key:
                    return
                self._request_date_summary_with_api(selected_files, range_label, api_key)

    def _build_date_prompt(self, files: List[Path], range_label: str) -> str:
        """Build AI prompt for date-based summary.

        Args:
            files: List of task files
            range_label: Descriptive label (e.g. "daily-2026-02-13")

        Returns:
            Prompt string
        """
        # Parse display label
        display_label = range_label.replace("-", " ", 1).replace("_to_", " ~ ")

        # Combine file contents
        combined_content = []
        combined_content.append(f"# {display_label}\n")
        combined_content.append(f"파일 개수: {len(files)}\n\n")

        for file in sorted(files, key=lambda x: x.name):
            combined_content.append(f"\n## 파일: {file.name}\n")
            content = file.read_text(encoding='utf-8')
            combined_content.append(content)
            combined_content.append("\n---\n")

        full_content = "\n".join(combined_content)

        prompt = f"""다음은 {display_label} 기간에 진행된 Claude와의 작업 로그를 정리한 마크다운 파일들입니다.

이 기간 전체에서 수행한 작업을 종합적으로 요약해주세요.

포함할 내용:
1. **기간 요약**: 이 기간에 무슨 일을 했는지 2-3문장으로 요약
2. **작업 목록**: 각 task 파일별로 시간(파일명의 HHMMSS)과 작업 내용을 개별적으로 전부 나열. 시간대로 묶지 말고 각 파일 하나하나를 별도 항목으로 표시. 형식 예시:
   - **15:42** - B2B 컨트롤러 비교 분석: MeetingController vs PsaMeetingController 비교
   - **15:59** - 서비스 레이어 심층 추적: 12건 이슈 발견 (CRITICAL 5건)
   - **16:03** - 버그 수정 적용: B2B 2건, PSA 5건
3. **주요 작업 흐름**: 전체 기간의 작업 흐름을 시간 순서대로 설명
4. **수정/생성된 파일**: 주요 파일 목록과 변경 내용
5. **핵심 기술적 결정사항**: 중요한 기술적 선택이나 해결 방법
6. **결과**: 최종적으로 무엇이 완성되었는지

마크다운 형식으로 작성해주세요.

---

{full_content}
"""
        return prompt

    def _save_date_summary(self, range_label: str, files: List[Path], ai_response: str) -> Path:
        """Save date-based summary file.

        Args:
            range_label: e.g. "daily-2026-02-13"
            files: List of task files included
            ai_response: AI-generated summary text

        Returns:
            Path to saved file
        """
        config = Config(self.config_path) if self.config_path.exists() else Config(None)
        summaries_dir = Path(config.get("output.summaries_directory", "./summaries"))
        summaries_dir.mkdir(parents=True, exist_ok=True)

        display_label = range_label.replace("-", " ", 1).replace("_to_", " ~ ")
        summary_path = summaries_dir / f"{range_label}_summary.md"

        summary_content = [
            f"# 기간 요약: {display_label}\n",
            f"**파일 개수**: {len(files)}",
            f"**포함된 파일들**:",
        ]
        for f in sorted(files, key=lambda x: x.name):
            summary_content.append(f"- [{f.name}]({f.name})")

        summary_content.append("\n---\n")
        summary_content.append(ai_response)

        summary_path.write_text("\n".join(summary_content), encoding='utf-8')
        return summary_path

    def _request_date_summary_with_claude_code(self, files: List[Path], range_label: str):
        """Request date-based summary using Claude Code CLI.

        Args:
            files: List of task files
            range_label: Descriptive label for the date range
        """
        import subprocess

        display_label = range_label.replace("-", " ", 1).replace("_to_", " ~ ")
        print(f"\n⏳ '{display_label}' 기간을 Claude Code로 요약 중...\n")

        try:
            prompt = self._build_date_prompt(files, range_label)

            project_root = Path(__file__).parent.parent
            result = subprocess.run(
                [
                    "claude",
                    "--print",
                    "--add-dir", str(project_root / "tasks")
                ],
                input=prompt,
                capture_output=True,
                text=True,
                cwd=str(project_root),
                timeout=120
            )

            if result.returncode != 0:
                print(f"  ❌ Claude Code 실행 오류: {result.stderr}")
                return

            summary = result.stdout.strip()
            summary_path = self._save_date_summary(range_label, files, summary)
            print(f"  ✓ 요약 완료: {summary_path.name}")

        except subprocess.TimeoutExpired:
            print(f"  ❌ 시간 초과 (2분)")
        except Exception as e:
            print(f"  ❌ 오류: {e}")
            import traceback
            traceback.print_exc()

    def _request_date_summary_with_api(self, files: List[Path], range_label: str, api_key: str):
        """Request date-based summary using Claude API.

        Args:
            files: List of task files
            range_label: Descriptive label for the date range
            api_key: Claude API key
        """
        try:
            from anthropic import Anthropic
        except ImportError:
            print("\n❌ anthropic 패키지가 설치되지 않았습니다.")
            print("   다음 명령으로 설치하세요: pip install anthropic\n")
            return

        client = Anthropic(api_key=api_key)
        display_label = range_label.replace("-", " ", 1).replace("_to_", " ~ ")
        print(f"\n⏳ '{display_label}' 기간을 API로 요약 중...\n")

        try:
            prompt = self._build_date_prompt(files, range_label)

            message = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=3000,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            summary = message.content[0].text
            summary_path = self._save_date_summary(range_label, files, summary)
            print(f"  ✓ 요약 완료: {summary_path.name}")

        except Exception as e:
            print(f"  ❌ 오류: {e}")
            import traceback
            traceback.print_exc()


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
