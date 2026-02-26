#!/bin/bash
# Install Claude Code hooks

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOKS_DIR="$HOME/.claude/hooks"

echo "Claude Code Hooks 설치"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Create hooks directory
mkdir -p "$HOOKS_DIR"

# Install stop hook
echo ""
echo "1. Stop Hook 설치 (대화 종료 시 자동 정리)"
if [ -f "$HOOKS_DIR/stop" ]; then
    read -p "   기존 stop hook이 있습니다. 덮어쓰시겠습니까? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "   건너뜀"
    else
        cp "$SCRIPT_DIR/claude-stop-hook.sh" "$HOOKS_DIR/stop"
        chmod +x "$HOOKS_DIR/stop"
        echo "   ✓ 설치됨: $HOOKS_DIR/stop"
    fi
else
    cp "$SCRIPT_DIR/claude-stop-hook.sh" "$HOOKS_DIR/stop"
    chmod +x "$HOOKS_DIR/stop"
    echo "   ✓ 설치됨: $HOOKS_DIR/stop"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "설치 완료!"
echo ""
echo "동작:"
echo "  - Claude Code 대화 종료 시 자동으로 로그 정리"
echo "  - 5개 세션마다 효율성 분석 자동 실행"
echo ""
echo "확인:"
echo "  ls -la ~/.claude/hooks/"
echo ""
echo "로그:"
echo "  tail -f organizer.log"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
