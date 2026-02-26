#!/usr/bin/env python3
"""CLI for prompt optimizer."""

import sys
import argparse
from pathlib import Path
from .generator import PromptGenerator


def optimize_command(args):
    """Optimize user input."""
    user_input = args.input if args.input else " ".join(args.words)

    if not user_input:
        print("에러: 입력이 필요합니다.", file=sys.stderr)
        sys.exit(1)

    # Get project root
    project_root = Path.cwd()
    if args.project:
        project_root = Path(args.project)

    # Generate optimized prompt
    generator = PromptGenerator(project_root)

    # Context-only mode for hooks
    if hasattr(args, 'context_only') and args.context_only:
        context = generator.generate_context_only(user_input)
        if context:
            print(context)
        return

    optimized = generator.generate(
        user_input,
        include_original=not args.no_original
    )

    # Calculate quality
    quality = generator.calculate_quality(optimized)

    # Output
    if args.quiet:
        print(optimized)
    else:
        print("=" * 60)
        print("보강된 프롬프트")
        print("=" * 60)
        print(optimized)
        print()
        print(f"품질 점수: {quality:.1%}")
        print("=" * 60)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="AI 프롬프트 최적화 도구",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  # 입력을 최적화
  prompt-optimizer optimize "debouncing 버그"

  # 원본 제외
  prompt-optimizer optimize "파일 확인" --no-original

  # 조용한 모드 (파이프라인용)
  prompt-optimizer optimize "에러" --quiet
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="명령어")

    # Optimize command
    optimize_parser = subparsers.add_parser("optimize", help="프롬프트 최적화")
    optimize_parser.add_argument(
        "words",
        nargs="*",
        help="최적화할 입력 (여러 단어 가능)"
    )
    optimize_parser.add_argument(
        "-i", "--input",
        help="입력 문자열 (인자 대신 사용 가능)"
    )
    optimize_parser.add_argument(
        "--no-original",
        action="store_true",
        help="원본 요청 제외"
    )
    optimize_parser.add_argument(
        "-p", "--project",
        help="프로젝트 루트 디렉토리"
    )
    optimize_parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="조용한 모드 (결과만 출력)"
    )
    optimize_parser.add_argument(
        "--context-only",
        action="store_true",
        help="추가 컨텍스트만 생성 (hooks용)"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "optimize":
        optimize_command(args)


if __name__ == "__main__":
    main()
