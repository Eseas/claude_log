"""Watch mode handlers and menu selection functions for the interactive CLI."""

import sys
from pathlib import Path
from typing import Optional

import inquirer

from claude_log_organizer.config import Config


def watch_from_config(cli):
    """Start watching using directories from config.

    Args:
        cli: InteractiveCLI instance
    """
    if not cli.config_path.exists():
        print("\n❌ 설정 파일이 없습니다. 먼저 'init' 명령으로 생성하세요.")
        return

    if not cli.app:
        from claude_log_organizer.main import LogOrganizerApp
        cli.app = LogOrganizerApp(cli.config_path)

    config = Config(cli.config_path)
    directories = config.get("watch.directories", ["./logs"])

    if isinstance(directories, str):
        directories = [directories]

    print("\n📂 설정된 디렉토리:")
    for i, d in enumerate(directories, 1):
        print(f"  {i}. {Path(d).absolute()}")

    print("\n⏳ 모니터링을 시작합니다...")
    print("   (Ctrl+C를 눌러 중지)\n")

    try:
        cli.app.watch()
    except KeyboardInterrupt:
        print("\n\n✓ 모니터링을 중지했습니다.\n")


def watch_from_manual_input(cli):
    """Start watching using manually input directories.

    Args:
        cli: InteractiveCLI instance
    """
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
    if not cli.app:
        from claude_log_organizer.main import LogOrganizerApp
        cli.app = LogOrganizerApp(cli.config_path if cli.config_path.exists() else None)

    # Temporarily override watch directories
    cli.app.config.data["watch"]["directories"] = directories

    print("\n⏳ 모니터링을 시작합니다...")
    print("   (Ctrl+C를 눌러 중지)\n")

    # Recreate watcher with new config
    from claude_log_organizer.watcher.file_watcher import ConversationLogWatcher
    cli.app.watcher = ConversationLogWatcher(cli.app.config)

    try:
        cli.app.watcher.start(callback=cli.app.dispatcher.dispatch_file_event)
    except KeyboardInterrupt:
        print("\n\n✓ 모니터링을 중지했습니다.\n")


def select_analysis_type() -> Optional[str]:
    """Select analysis type.

    Returns:
        'summary', 'efficiency', 'timeline', 'token_analysis', 'task_success', or None if cancelled
    """
    questions = [
        inquirer.List(
            "type",
            message="분석 타입을 선택하세요",
            choices=[
                ("일반 요약 - 세션 작업 내용 요약", "summary"),
                ("효율성 분석 - 프롬프트 효율성 + 개선 제안", "efficiency"),
                ("타임라인 다이어그램 - 시간대별 작업 시각화 (.drawio)", "timeline"),
                ("토큰 사용량 분석 - 고사용 세션 식별 + 감량 전략", "token_analysis"),
                ("작업 성공/실패 분석 - 시그널 + AI 판정", "task_success"),
                ("취소", "cancel"),
            ],
        )
    ]

    answers = inquirer.prompt(questions)
    if not answers or answers["type"] == "cancel":
        return None

    return answers["type"]


def select_ai_method() -> Optional[str]:
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


def select_grouping_mode() -> Optional[str]:
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


def select_date_mode() -> Optional[str]:
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


def get_api_key(config_path: Path) -> Optional[str]:
    """Get API key from config or user input.

    Args:
        config_path: Path to configuration file

    Returns:
        API key or None if cancelled
    """
    config = Config(config_path) if config_path.exists() else Config(None)

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
            with open(config_path, 'w') as f:
                yaml.dump(config.data, f, default_flow_style=False, allow_unicode=True)
            print("✓ 저장되었습니다.")

    return api_key
