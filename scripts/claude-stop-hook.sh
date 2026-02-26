#!/bin/bash
# Claude Code Stop Hook - 대화 종료 시 자동으로 효율성 분석 실행
#
# 설치:
#   mkdir -p ~/.claude/hooks
#   cp scripts/claude-stop-hook.sh ~/.claude/hooks/stop
#   chmod +x ~/.claude/hooks/stop

set -euo pipefail

# Configuration
PROJECT_ROOT="/Users/eseas/Desktop/mine/claude_log"
LOG_FILE="$PROJECT_ROOT/organizer.log"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Claude session stopped" >> "$LOG_FILE"

# Wait for log file to be written
sleep 2

# Get session ID from last log file
SESSION_LOG=$(ls -t ~/.claude/logs/*.log 2>/dev/null | head -n 1)

if [ -n "$SESSION_LOG" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Processing session log: $SESSION_LOG" >> "$LOG_FILE"

    # Process log file with organizer (runs in background)
    (cd "$PROJECT_ROOT" && python3 -m claude_log_organizer.cli process "$SESSION_LOG" >> "$LOG_FILE" 2>&1) &

    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Background processing started" >> "$LOG_FILE"
fi

# Optional: Auto-analyze efficiency after N sessions
SESSION_COUNT=$(ls -1 "$PROJECT_ROOT/tasks/task-*.md" 2>/dev/null | wc -l)

if [ $((SESSION_COUNT % 5)) -eq 0 ] && [ "$SESSION_COUNT" -gt 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Auto-analyzing efficiency ($SESSION_COUNT sessions)" >> "$LOG_FILE"

    # Run efficiency analysis in background
    (cd "$PROJECT_ROOT" && python3 -m claude_log_organizer.interactive --auto-analyze >> "$LOG_FILE" 2>&1) &
fi

exit 0
