"""Analysis execution functions for the interactive CLI."""

from pathlib import Path
from typing import List

from claude_log_organizer.config import Config
from claude_log_organizer.output import out
from claude_log_organizer.interactive.file_discovery import get_summaries_dir


def request_ai_summary_by_session(sessions: dict, selected_sessions: List[str], api_key: str, config_path: Path):
    """Request AI summary for selected sessions using the API.

    Args:
        sessions: Dictionary mapping session ID to list of files
        selected_sessions: List of session IDs to summarize
        api_key: Claude API key
        config_path: Path to configuration file
    """
    try:
        from anthropic import Anthropic
    except ImportError:
        out.print("\n❌ anthropic 패키지가 설치되지 않았습니다.")
        out.print("   다음 명령으로 설치하세요: pip install anthropic\n")
        return

    client = Anthropic(api_key=api_key)

    out.print(f"\n⏳ {len(selected_sessions)}개 세션을 AI로 요약 중...\n")

    for i, session_id in enumerate(selected_sessions, 1):
        files = sessions[session_id]
        out.print(f"[{i}/{len(selected_sessions)}] Session: {session_id[:8]}... ({len(files)}개 파일)")

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
            summaries_dir = get_summaries_dir(files, config_path)
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

            out.print(f"  ✓ 요약 완료: {summary_path.name}")

        except Exception as e:
            out.print(f"  ❌ 오류: {e}")
            import traceback
            traceback.print_exc()

    out.print(f"\n✓ 완료! {len(selected_sessions)}개 세션 요약 생성됨\n")


def request_ai_summary_with_claude_code(sessions: dict, selected_sessions: List[str], config_path: Path):
    """Request AI summary using Claude Code CLI.

    Args:
        sessions: Dictionary mapping session ID to list of files
        selected_sessions: List of session IDs to summarize
        config_path: Path to configuration file
    """
    import subprocess

    out.print(f"\n⏳ {len(selected_sessions)}개 세션을 Claude Code로 요약 중...\n")

    for i, session_id in enumerate(selected_sessions, 1):
        files = sessions[session_id]
        out.print(f"[{i}/{len(selected_sessions)}] Session: {session_id[:8]}... ({len(files)}개 파일)")

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
            project_root = Path(__file__).parent.parent.parent

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
                out.print(f"  ❌ Claude Code 실행 오류: {result.stderr}")
                continue

            summary = result.stdout.strip()

            # Save summary with session ID
            summaries_dir = get_summaries_dir(files, config_path)
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

            out.print(f"  ✓ 요약 완료: {summary_path.name}")

        except subprocess.TimeoutExpired:
            out.print(f"  ❌ 시간 초과 (2분)")
        except Exception as e:
            out.print(f"  ❌ 오류: {e}")
            import traceback
            traceback.print_exc()

    out.print(f"\n✓ 완료! {len(selected_sessions)}개 세션 요약 생성됨\n")


def request_efficiency_analysis_with_claude_code(sessions: dict, selected_sessions: List[str], config_path: Path):
    """Request efficiency analysis using Claude Code CLI.

    Args:
        sessions: Dictionary mapping session ID to list of files
        selected_sessions: List of session IDs to analyze
        config_path: Path to configuration file
    """
    import subprocess
    import sys

    # Add prompt_optimizer to path
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))

    from prompt_optimizer.analyzers import SessionAnalyzer

    analyzer = SessionAnalyzer()

    out.print(f"\n⏳ {len(selected_sessions)}개 세션을 효율성 분석 중...\n")

    for i, session_id in enumerate(selected_sessions, 1):
        files = sessions[session_id]
        out.print(f"[{i}/{len(selected_sessions)}] Session: {session_id[:8]}... ({len(files)}개 파일)")

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
                out.print(f"  ❌ Claude Code 실행 오류: {result.stderr}")
                continue

            analysis = result.stdout.strip()

            # Save efficiency analysis
            summaries_dir = get_summaries_dir(files, config_path)
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

            out.print(f"  ✓ 분석 완료: {analysis_path.name}")

        except subprocess.TimeoutExpired:
            out.print(f"  ❌ 시간 초과 (3분)")
        except Exception as e:
            out.print(f"  ❌ 오류: {e}")
            import traceback
            traceback.print_exc()

    out.print(f"\n✓ 완료! {len(selected_sessions)}개 세션 효율성 분석 생성됨\n")


def request_efficiency_analysis_with_api(sessions: dict, selected_sessions: List[str], api_key: str, config_path: Path):
    """Request efficiency analysis using Claude API.

    Args:
        sessions: Dictionary mapping session ID to list of files
        selected_sessions: List of session IDs to analyze
        api_key: Claude API key
        config_path: Path to configuration file
    """
    try:
        from anthropic import Anthropic
    except ImportError:
        out.print("\n❌ anthropic 패키지가 설치되지 않았습니다.")
        out.print("   다음 명령으로 설치하세요: pip install anthropic\n")
        return

    import sys

    # Add prompt_optimizer to path
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))

    from prompt_optimizer.analyzers import SessionAnalyzer

    analyzer = SessionAnalyzer()
    client = Anthropic(api_key=api_key)

    out.print(f"\n⏳ {len(selected_sessions)}개 세션을 효율성 분석 중...\n")

    for i, session_id in enumerate(selected_sessions, 1):
        files = sessions[session_id]
        out.print(f"[{i}/{len(selected_sessions)}] Session: {session_id[:8]}... ({len(files)}개 파일)")

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
            summaries_dir = get_summaries_dir(files, config_path)
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

            out.print(f"  ✓ 분석 완료: {analysis_path.name}")

        except Exception as e:
            out.print(f"  ❌ 오류: {e}")
            import traceback
            traceback.print_exc()

    out.print(f"\n✓ 완료! {len(selected_sessions)}개 세션 효율성 분석 생성됨\n")


def handle_date_based_summary(task_files: List[Path], config_path: Path):
    """Handle date-based summarization flow.

    Args:
        task_files: All task files from the output directory
        config_path: Path to configuration file
    """
    from claude_log_organizer.interactive.file_discovery import (
        group_files_by_date,
        find_log_files_for_task_files,
        select_daily,
        select_weekly,
        select_custom_range,
    )
    from claude_log_organizer.interactive.handlers import (
        select_analysis_type,
        select_ai_method,
        select_date_mode,
        get_api_key,
    )

    date_groups = group_files_by_date(task_files)

    if not date_groups:
        out.print("\n--- 날짜 형식의 task 파일이 없습니다.")
        out.print("    (task-YYYY-MM-DD_HHMMSS_UUID.md 형식만 지원)\n")
        return

    available_dates = sorted(date_groups.keys())
    out.print(f"\n--- 사용 가능한 날짜 범위: {available_dates[0]} ~ {available_dates[-1]}")
    out.print(f"    총 {len(available_dates)}일, {sum(len(v) for v in date_groups.values())}개 파일\n")

    # Select date mode
    date_mode = select_date_mode()
    if not date_mode:
        return

    # Get files for selected date range
    if date_mode == "daily":
        selected_files, range_label = select_daily(date_groups, available_dates)
    elif date_mode == "weekly":
        selected_files, range_label = select_weekly(date_groups, available_dates, config_path)
    elif date_mode == "custom":
        selected_files, range_label = select_custom_range(date_groups, available_dates)
    else:
        return

    if not selected_files:
        return

    out.print(f"\n✓ 선택된 파일: {len(selected_files)}개")

    # Reuse existing analysis type + AI method selection
    analysis_type = select_analysis_type()
    if not analysis_type:
        return

    # Timeline diagram doesn't need AI
    if analysis_type == "timeline":
        generate_timeline_diagram(selected_files, range_label, config_path)
        return

    # Token analysis doesn't need AI
    if analysis_type == "token_analysis":
        generate_token_analysis(selected_files, range_label, config_path)
        return

    # Task success analysis
    if analysis_type == "task_success":
        log_files = find_log_files_for_task_files(selected_files, config_path)
        generate_task_success_analysis(log_files, range_label, config_path)
        return

    ai_method = select_ai_method()
    if not ai_method:
        return

    if analysis_type == "summary":
        if ai_method == "claude_code":
            request_date_summary_with_claude_code(selected_files, range_label, config_path)
        else:
            api_key = get_api_key(config_path)
            if not api_key:
                return
            request_date_summary_with_api(selected_files, range_label, api_key, config_path)
    else:
        if ai_method == "claude_code":
            request_date_summary_with_claude_code(selected_files, range_label, config_path)
        else:
            api_key = get_api_key(config_path)
            if not api_key:
                return
            request_date_summary_with_api(selected_files, range_label, api_key, config_path)


def generate_timeline_diagram(files: List[Path], range_label: str, config_path: Path):
    """Generate timeline diagram without AI.

    Args:
        files: List of task files
        range_label: Descriptive label for the date range
        config_path: Path to configuration file
    """
    from claude_log_organizer.generators.timeline import TimelineDiagramGenerator

    out.print(f"\n⏳ 타임라인 다이어그램 생성 중...\n")

    try:
        generator = TimelineDiagramGenerator()
        summaries_dir = get_summaries_dir(files, config_path)
        summaries_dir.mkdir(parents=True, exist_ok=True)

        output_path = summaries_dir / f"{range_label}_timeline.drawio"
        generator.generate(files, range_label, output_path)
        out.print(f"  ✓ 타임라인 저장: {output_path}")
        out.print(f"    (VS Code draw.io 확장 또는 diagrams.net에서 열기)\n")

    except ValueError as e:
        out.print(f"  ❌ {e}\n")
    except Exception as e:
        out.print(f"  ❌ 오류: {e}")
        import traceback
        traceback.print_exc()


def generate_token_analysis(files: List[Path], range_label: str, config_path: Path):
    """Generate token usage analysis without AI.

    Args:
        files: List of task files
        range_label: Descriptive label for the date range
        config_path: Path to configuration file
    """
    from claude_log_organizer.generators.timeline import TimelineDiagramGenerator

    out.print(f"\n⏳ 토큰 사용량 분석 중...\n")

    try:
        generator = TimelineDiagramGenerator()
        entries = generator.parse_task_files(files)

        if not entries:
            out.print("  ❌ 분석 가능한 task 파일이 없습니다.\n")
            return

        analysis_lines = generator._analyze_token_usage(entries)

        if not analysis_lines:
            out.print("  ℹ️  토큰 데이터가 부족하거나 고사용 세션이 없습니다.")
            out.print("     (최소 2개 이상의 토큰 데이터가 있는 세션이 필요합니다)\n")
            return

        # Build output
        summaries_dir = get_summaries_dir(files, config_path)
        summaries_dir.mkdir(parents=True, exist_ok=True)

        output_path = summaries_dir / f"{range_label}_token_analysis.md"

        # Add header
        display_label = range_label.replace("-", " ", 1).replace("_to_", " ~ ")
        content_lines = [
            f"# Token Usage Analysis: {display_label}",
            f"",
            f"**분석 대상**: {len(files)}개 파일, {len(entries)}개 세션",
            f"",
            "---",
            "",
        ]
        content_lines.extend(analysis_lines)
        content_lines.append("")
        content_lines.append("---")
        content_lines.append("*Generated by Claude Log Organizer*")

        output_path.write_text("\n".join(content_lines), encoding="utf-8")

        # Also print summary to console (rich-rendered markdown)
        out.print(f"  ✓ 분석 완료: {output_path}")
        out.print()
        out.markdown("\n".join(analysis_lines))
        out.print()

    except Exception as e:
        out.print(f"  ❌ 오류: {e}")
        import traceback
        traceback.print_exc()


def generate_task_success_analysis(log_files: List[Path], range_label: str, config_path: Path):
    """Generate task success/failure analysis.

    Args:
        log_files: List of .log files to analyze
        range_label: Descriptive label
        config_path: Path to configuration file
    """
    import inquirer
    from claude_log_organizer.analyzers.task_success_analyzer import TaskSuccessAnalyzer

    if not log_files:
        out.print("\n  ❌ 분석할 로그 파일을 찾을 수 없습니다.")
        out.print("     (.claude/logs/ 디렉토리에 해당 세션의 로그가 있는지 확인하세요)\n")
        return

    # Ask whether to use AI
    use_ai = False
    try:
        questions = [
            inquirer.List(
                "ai",
                message="AI 분석도 함께 실행할까요? (Claude CLI 필요)",
                choices=[
                    ("시그널 분석만 (빠름)", False),
                    ("시그널 + AI 분석 (더 정확)", True),
                ],
            )
        ]
        answers = inquirer.prompt(questions)
        if answers:
            use_ai = answers["ai"]
    except Exception:
        pass

    out.print(f"\n⏳ 작업 성공/실패 분석 중... ({len(log_files)}개 로그 파일)\n")

    try:
        analyzer = TaskSuccessAnalyzer()
        all_interactions = analyzer.analyze_log_files(log_files, use_ai=use_ai)

        if not all_interactions:
            out.print("  ❌ 분석 가능한 상호작용이 없습니다.\n")
            return

        report_lines = analyzer.generate_report(all_interactions)

        # Build output file -- derive summaries dir from log file's project root
        # log_files are in {project}/.claude/logs/, so project = parent.parent.parent
        if log_files and log_files[0].parent.name == "logs" and log_files[0].parent.parent.name == ".claude":
            summaries_dir = log_files[0].parent.parent.parent / "summaries"
        else:
            config = Config(config_path) if config_path.exists() else Config(None)
            summaries_dir = Path(config.get("output.summaries_directory", "./summaries"))
        summaries_dir.mkdir(parents=True, exist_ok=True)

        output_path = summaries_dir / f"{range_label}_task_success.md"

        display_label = range_label.replace("-", " ", 1).replace("_to_", " ~ ")
        content_lines = [
            f"# Task Success Analysis: {display_label}",
            f"",
            f"**분석 대상**: {len(log_files)}개 로그 파일, {len(all_interactions)}개 상호작용",
            f"**분석 방법**: 시그널 기반" + (" + AI 기반" if use_ai else ""),
            f"",
            "---",
            "",
        ]
        content_lines.extend(report_lines)
        content_lines.append("")
        content_lines.append("---")
        content_lines.append("*Generated by Claude Log Organizer*")

        output_path.write_text("\n".join(content_lines), encoding="utf-8")

        # Print to console (rich-rendered markdown)
        out.print(f"  ✓ 분석 완료: {output_path}")
        out.print()
        out.markdown("\n".join(report_lines))
        out.print()

    except Exception as e:
        out.print(f"  ❌ 오류: {e}")
        import traceback
        traceback.print_exc()


def build_date_prompt(files: List[Path], range_label: str) -> str:
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


def save_date_summary(range_label: str, files: List[Path], ai_response: str, config_path: Path) -> Path:
    """Save date-based summary file.

    Args:
        range_label: e.g. "daily-2026-02-13"
        files: List of task files included
        ai_response: AI-generated summary text
        config_path: Path to configuration file

    Returns:
        Path to saved file
    """
    summaries_dir = get_summaries_dir(files, config_path)
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


def request_date_summary_with_claude_code(files: List[Path], range_label: str, config_path: Path):
    """Request date-based summary using Claude Code CLI.

    Args:
        files: List of task files
        range_label: Descriptive label for the date range
        config_path: Path to configuration file
    """
    import subprocess

    display_label = range_label.replace("-", " ", 1).replace("_to_", " ~ ")
    out.print(f"\n⏳ '{display_label}' 기간을 Claude Code로 요약 중...\n")

    try:
        prompt = build_date_prompt(files, range_label)

        project_root = Path(__file__).parent.parent.parent
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
            out.print(f"  ❌ Claude Code 실행 오류: {result.stderr}")
            return

        summary = result.stdout.strip()
        summary_path = save_date_summary(range_label, files, summary, config_path)
        out.print(f"  ✓ 요약 완료: {summary_path.name}")

    except subprocess.TimeoutExpired:
        out.print(f"  ❌ 시간 초과 (2분)")
    except Exception as e:
        out.print(f"  ❌ 오류: {e}")
        import traceback
        traceback.print_exc()


def request_date_summary_with_api(files: List[Path], range_label: str, api_key: str, config_path: Path):
    """Request date-based summary using Claude API.

    Args:
        files: List of task files
        range_label: Descriptive label for the date range
        api_key: Claude API key
        config_path: Path to configuration file
    """
    try:
        from anthropic import Anthropic
    except ImportError:
        out.print("\n❌ anthropic 패키지가 설치되지 않았습니다.")
        out.print("   다음 명령으로 설치하세요: pip install anthropic\n")
        return

    client = Anthropic(api_key=api_key)
    display_label = range_label.replace("-", " ", 1).replace("_to_", " ~ ")
    out.print(f"\n⏳ '{display_label}' 기간을 API로 요약 중...\n")

    try:
        prompt = build_date_prompt(files, range_label)

        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=3000,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )

        summary = message.content[0].text
        summary_path = save_date_summary(range_label, files, summary, config_path)
        out.print(f"  ✓ 요약 완료: {summary_path.name}")

    except Exception as e:
        out.print(f"  ❌ 오류: {e}")
        import traceback
        traceback.print_exc()
