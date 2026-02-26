#!/bin/bash
# Setup auto-optimize for Claude

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUTO_OPTIMIZE="$SCRIPT_DIR/auto-optimize.sh"

# Detect shell
SHELL_RC=""
if [ -n "$ZSH_VERSION" ]; then
    SHELL_RC="$HOME/.zshrc"
elif [ -n "$BASH_VERSION" ]; then
    SHELL_RC="$HOME/.bashrc"
else
    echo "지원되지 않는 셸입니다."
    exit 1
fi

echo "Claude 자동 최적화 설정"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "이 설정은 'claude' 명령어를 자동으로 최적화하는 버전으로 대체합니다."
echo ""
echo "동작:"
echo "  claude \"버그\" → 자동 최적화 → Claude Code 호출"
echo ""
read -p "설치하시겠습니까? (y/N): " -n 1 -r
echo

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "취소되었습니다."
    exit 0
fi

# Add to shell RC
if grep -q "auto-optimize.sh" "$SHELL_RC" 2>/dev/null; then
    echo ""
    echo "✓ 이미 설정되어 있습니다: $SHELL_RC"
else
    echo "" >> "$SHELL_RC"
    echo "# Claude Auto-Optimize" >> "$SHELL_RC"
    echo "source $AUTO_OPTIMIZE" >> "$SHELL_RC"
    echo ""
    echo "✓ 설정이 추가되었습니다: $SHELL_RC"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "설치 완료!"
echo ""
echo "적용:"
echo "  source $SHELL_RC"
echo ""
echo "또는 새 터미널 열기"
echo ""
echo "사용법:"
echo "  claude \"버그 수정\"              # 자동 최적화 ✨"
echo "  claude --optimize-interactive \"버그\"  # 확인 후 진행"
echo "  claude --no-optimize \"원본\"           # 최적화 안함"
echo ""
echo "비활성화:"
echo "  unset -f claude"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
