#!/bin/bash
# Test Claude Code hooks behavior

HOOKS_DIR="$HOME/.claude/hooks"
LOG_FILE="$HOME/.claude/hook-test.log"

mkdir -p "$HOOKS_DIR"

# Create test start hook
cat > "$HOOKS_DIR/start" << 'EOF'
#!/bin/bash
echo "[$(date '+%Y-%m-%d %H:%M:%S.%3N')] START hook triggered" >> "$HOME/.claude/hook-test.log"
echo "  Args: $@" >> "$HOME/.claude/hook-test.log"
echo "  PWD: $PWD" >> "$HOME/.claude/hook-test.log"
echo "  ENV: $(env | grep CLAUDE)" >> "$HOME/.claude/hook-test.log"
echo "" >> "$HOME/.claude/hook-test.log"
EOF

# Create test stop hook
cat > "$HOOKS_DIR/stop" << 'EOF'
#!/bin/bash
echo "[$(date '+%Y-%m-%d %H:%M:%S.%3N')] STOP hook triggered" >> "$HOME/.claude/hook-test.log"
echo "  Args: $@" >> "$HOME/.claude/hook-test.log"
echo "  PWD: $PWD" >> "$HOME/.claude/hook-test.log"
echo "" >> "$HOME/.claude/hook-test.log"
EOF

# Make executable
chmod +x "$HOOKS_DIR/start"
chmod +x "$HOOKS_DIR/stop"

# Clear log
> "$LOG_FILE"

echo "테스트 hooks 설치 완료!"
echo ""
echo "테스트 방법:"
echo "1. Claude Code 실행: claude"
echo "2. 메시지 1 전송"
echo "3. 메시지 2 전송"
echo "4. 세션 종료 (Ctrl+D 또는 exit)"
echo "5. 로그 확인: cat ~/.claude/hook-test.log"
echo ""
echo "예상 결과:"
echo "  - start가 세션당 1회: START 1번만 기록"
echo "  - start가 메시지마다: START 여러 번 기록"
echo ""
echo "로그 파일: $LOG_FILE"
