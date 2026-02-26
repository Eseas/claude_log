#!/bin/bash
# Smart Claude - Auto-optimize prompts before sending to Claude Code

set -euo pipefail

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
OPTIMIZER="$PROJECT_ROOT/prompt_optimizer/cli.py"

# Help
if [ $# -eq 0 ] || [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
    cat <<EOF
Smart Claude - AI 프롬프트 자동 최적화

사용법:
  smart-claude "your prompt"
  smart-claude --interactive "your prompt"
  smart-claude --dry-run "your prompt"

옵션:
  -i, --interactive    최적화 결과 확인 후 진행
  -d, --dry-run        최적화만 수행 (Claude 호출 안함)
  -n, --no-optimize    최적화 없이 바로 전송
  -h, --help           도움말 표시

예시:
  smart-claude "debouncing 버그"
  smart-claude --interactive "파일 이상해"
  smart-claude --dry-run "에러 확인"
EOF
    exit 0
fi

# Parse options
INTERACTIVE=false
DRY_RUN=false
NO_OPTIMIZE=false
USER_INPUT=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -i|--interactive)
            INTERACTIVE=true
            shift
            ;;
        -d|--dry-run)
            DRY_RUN=true
            shift
            ;;
        -n|--no-optimize)
            NO_OPTIMIZE=true
            shift
            ;;
        *)
            USER_INPUT="$USER_INPUT $1"
            shift
            ;;
    esac
done

USER_INPUT=$(echo "$USER_INPUT" | xargs)  # Trim whitespace

if [ -z "$USER_INPUT" ]; then
    echo "에러: 입력이 필요합니다."
    echo "사용법: smart-claude \"your prompt\""
    exit 1
fi

# Step 1: Optimize prompt
if [ "$NO_OPTIMIZE" = true ]; then
    OPTIMIZED="$USER_INPUT"
    echo -e "${BLUE}[최적화 건너뜀]${NC}"
else
    echo -e "${BLUE}[프롬프트 최적화 중...]${NC}"

    if ! OPTIMIZED=$(python3 "$OPTIMIZER" optimize --quiet "$USER_INPUT"); then
        echo "경고: 최적화 실패. 원본 사용."
        OPTIMIZED="$USER_INPUT"
    fi
fi

# Step 2: Show optimization result
if [ "$DRY_RUN" = true ] || [ "$INTERACTIVE" = true ]; then
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "${GREEN}보강된 프롬프트:${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "$OPTIMIZED"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
fi

# Step 3: Dry run exits here
if [ "$DRY_RUN" = true ]; then
    echo -e "${YELLOW}[Dry run - Claude 호출 안함]${NC}"
    exit 0
fi

# Step 4: Interactive confirmation
if [ "$INTERACTIVE" = true ]; then
    read -p "이 프롬프트로 Claude를 호출하시겠습니까? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "취소되었습니다."
        exit 0
    fi
fi

# Step 5: Call Claude Code
echo -e "${BLUE}[Claude Code 호출 중...]${NC}"
echo ""

# Check if claude command exists
if ! command -v claude &> /dev/null; then
    echo "에러: Claude Code CLI를 찾을 수 없습니다."
    echo "설치: https://claude.ai/download"
    exit 1
fi

# Call Claude with optimized prompt
echo "$OPTIMIZED" | claude --print

# Success
echo ""
echo -e "${GREEN}✓ 완료${NC}"
