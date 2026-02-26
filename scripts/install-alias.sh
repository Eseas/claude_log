#!/bin/bash
# Install smart-claude alias

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SMART_CLAUDE="$SCRIPT_DIR/smart-claude.sh"

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

# Add alias
ALIAS_LINE="alias smart-claude='$SMART_CLAUDE'"

if grep -q "smart-claude" "$SHELL_RC"; then
    echo "✓ 별칭이 이미 설정되어 있습니다: $SHELL_RC"
else
    echo "" >> "$SHELL_RC"
    echo "# Smart Claude - AI Prompt Optimizer" >> "$SHELL_RC"
    echo "$ALIAS_LINE" >> "$SHELL_RC"
    echo "✓ 별칭이 추가되었습니다: $SHELL_RC"
    echo ""
    echo "다음 명령으로 적용하세요:"
    echo "  source $SHELL_RC"
fi

echo ""
echo "사용법:"
echo "  smart-claude \"your prompt\""
echo "  smart-claude --interactive \"your prompt\""
echo "  smart-claude --dry-run \"your prompt\""
