#!/bin/bash
# Claude Code Start Hook - 메시지 전송 시 자동 최적화
#
# 주의: start hook이 메시지마다 실행되는 경우에만 작동
#
# 설치:
#   cp scripts/start-hook-optimizer.sh ~/.claude/hooks/start
#   chmod +x ~/.claude/hooks/start

set -euo pipefail

PROJECT_ROOT="/Users/eseas/Desktop/mine/claude_log"
LOG_FILE="$PROJECT_ROOT/hook-optimizer.log"

# 로깅
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Start hook triggered" >> "$LOG_FILE"
echo "  Args: $*" >> "$LOG_FILE"
echo "  Env: $(env | grep CLAUDE || echo 'No CLAUDE env')" >> "$LOG_FILE"

# TODO: 사용자 입력을 받을 수 있다면 여기서 최적화
# 하지만 start hook이 입력을 받을 수 있는지는 불확실

# 입력을 stdin으로 받을 수 있는지 테스트
if [ -p /dev/stdin ]; then
    echo "  STDIN available" >> "$LOG_FILE"

    # 입력 읽기 시도 (timeout 1초)
    if read -t 1 input 2>/dev/null; then
        echo "  Input received: $input" >> "$LOG_FILE"

        # 최적화 시도
        if optimized=$(python3 "$PROJECT_ROOT/prompt_optimizer/cli.py" optimize --quiet "$input" 2>/dev/null); then
            echo "  Optimized: $optimized" >> "$LOG_FILE"

            # 최적화된 입력 출력 (Claude에게 전달?)
            echo "$optimized"
        else
            # 최적화 실패 시 원본
            echo "$input"
        fi
    fi
else
    echo "  STDIN not available" >> "$LOG_FILE"
fi

exit 0
