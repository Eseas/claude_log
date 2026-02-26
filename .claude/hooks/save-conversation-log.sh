#!/bin/bash
# Claude Code 대화 내역을 .log 파일로 저장하는 Hook 스크립트
# 추출 태그: [USER], [ASSISTANT], [TOOL], [THINKING], [TOOL_RESULT],
#            [DOCUMENT], [PROGRESS], [SNAPSHOT], [COMPACT]

INPUT=$(cat)
TRANSCRIPT_PATH=$(echo "$INPUT" | jq -r '.transcript_path')
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id')
PROJECT_DIR=$(echo "$INPUT" | jq -r '.cwd')

# 로그 저장 디렉토리
LOG_DIR="$PROJECT_DIR/.claude/logs"
mkdir -p "$LOG_DIR"

# 파일명: 날짜_시분초_세션ID.log (매 턴마다 새 파일 생성)
DATE=$(date '+%Y-%m-%d_%H%M%S')
LOG_FILE="$LOG_DIR/${DATE}_${SESSION_ID}.log"

# transcript JSONL → 읽기 쉬운 .log 변환
if [ -f "$TRANSCRIPT_PATH" ]; then
  echo "=== Claude Code Session Log ===" > "$LOG_FILE"
  echo "Session ID: $SESSION_ID" >> "$LOG_FILE"
  echo "Project: $PROJECT_DIR" >> "$LOG_FILE"
  echo "Saved at: $(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG_FILE"
  echo "================================" >> "$LOG_FILE"
  echo "" >> "$LOG_FILE"

  # Hook context 파일이 있으면 로그에 포함
  HOOK_CONTEXT_FILE="$HOME/.claude/hook-contexts/${SESSION_ID}.jsonl"
  if [ -f "$HOOK_CONTEXT_FILE" ]; then
    echo "--- Hook Contexts (UserPromptSubmit) ---" >> "$LOG_FILE"
    while IFS= read -r hline; do
      TS=$(echo "$hline" | jq -r '.timestamp // empty')
      HPROMPT=$(echo "$hline" | jq -r '.prompt // empty' | head -c 100)
      HCTX=$(echo "$hline" | jq -r '.context // empty')
      echo "[HOOK $TS] prompt: ${HPROMPT}..." >> "$LOG_FILE"
      echo "  context: $HCTX" >> "$LOG_FILE"
      echo "" >> "$LOG_FILE"
    done < "$HOOK_CONTEXT_FILE"
    echo "--- End Hook Contexts ---" >> "$LOG_FILE"
    echo "" >> "$LOG_FILE"
  fi

  while IFS= read -r line; do
    # 실제 구조: {"type": "user"|"assistant", "message": {"role": "...", "content": ...}}
    TYPE=$(echo "$line" | jq -r '.type // empty')

    if [ "$TYPE" = "user" ]; then
      TEXT=$(echo "$line" | jq -r '
        .message.content as $c |
        if $c | type == "array" then
          [$c[] | select(.type == "text") | .text] | join("\n")
        elif $c | type == "string" then
          $c
        else
          empty
        end
      ')
      if [ -n "$TEXT" ]; then
        echo "[USER] $TEXT" >> "$LOG_FILE"
        echo "" >> "$LOG_FILE"
      fi

      # 첨부 문서 추출
      DOCUMENTS=$(echo "$line" | jq -r '
        .message.content as $c |
        if $c | type == "array" then
          [$c[] | select(.type == "document") | "[DOCUMENT] " + (.title // "untitled")] | join("\n")
        else empty end
      ')
      if [ -n "$DOCUMENTS" ]; then
        echo "$DOCUMENTS" >> "$LOG_FILE"
        echo "" >> "$LOG_FILE"
      fi

      # 도구 실행 결과 추출 (300자 제한)
      TOOL_RESULTS=$(echo "$line" | jq -r '
        .message.content as $c |
        if $c | type == "array" then
          [$c[] | select(.type == "tool_result") |
            "[TOOL_RESULT] " + (
              if .content | type == "array" then
                [.content[] | select(.type == "text") | .text[:300]] | join(" ")
              elif .content | type == "string" then .content[:300]
              else "" end
            )
          ] | join("\n")
        else empty end
      ')
      if [ -n "$TOOL_RESULTS" ]; then
        echo "$TOOL_RESULTS" >> "$LOG_FILE"
        echo "" >> "$LOG_FILE"
      fi

    elif [ "$TYPE" = "assistant" ]; then
      # 사고 과정 추출
      THINKING=$(echo "$line" | jq -r '
        .message.content as $c |
        if $c | type == "array" then
          [$c[] | select(.type == "thinking") | .thinking] | join("\n---\n")
        else empty end
      ')
      if [ -n "$THINKING" ]; then
        echo "[THINKING] $THINKING" >> "$LOG_FILE"
        echo "" >> "$LOG_FILE"
      fi

      # 텍스트 응답 추출
      TEXT=$(echo "$line" | jq -r '
        .message.content as $c |
        if $c | type == "array" then
          [$c[] | select(.type == "text") | .text] | join("\n")
        elif $c | type == "string" then
          $c
        else
          empty
        end
      ')
      if [ -n "$TEXT" ] && [ "$TEXT" != $'\n\n' ]; then
        echo "[ASSISTANT] $TEXT" >> "$LOG_FILE"
        echo "" >> "$LOG_FILE"
      fi

      # 도구 호출 추출
      TOOLS=$(echo "$line" | jq -r '
        .message.content as $c |
        if $c | type == "array" then
          [ $c[] | select(.type == "tool_use") |
            "[TOOL] " + .name +
            (if .name == "Bash" then " → " + (.input.command // "" | split("\n")[0])
             elif .name == "Read" then " → " + (.input.file_path // "")
             elif .name == "Write" then " → " + (.input.file_path // "")
             elif .name == "Edit" then " → " + (.input.file_path // "")
             elif .name == "Glob" then " → " + (.input.pattern // "")
             elif .name == "Grep" then " → " + (.input.pattern // "")
             else ""
             end)
          ] | join("\n")
        else
          empty
        end
      ')
      if [ -n "$TOOLS" ]; then
        echo "$TOOLS" >> "$LOG_FILE"
        echo "" >> "$LOG_FILE"
      fi

    elif [ "$TYPE" = "progress" ]; then
      # 서브에이전트 진행 상황
      MSG=$(echo "$line" | jq -r '.data.message // empty' | head -c 200)
      if [ -n "$MSG" ]; then
        echo "[PROGRESS] $MSG" >> "$LOG_FILE"
      fi

    elif [ "$TYPE" = "file-history-snapshot" ]; then
      # 파일 수정 스냅샷
      FILES_COUNT=$(echo "$line" | jq -r '.snapshot.trackedFileBackups | length')
      if [ "$FILES_COUNT" != "0" ] && [ "$FILES_COUNT" != "null" ] && [ -n "$FILES_COUNT" ]; then
        echo "[SNAPSHOT] $FILES_COUNT files tracked" >> "$LOG_FILE"
      fi

    elif [ "$TYPE" = "system" ]; then
      # 컨텍스트 압축
      SUBTYPE=$(echo "$line" | jq -r '.subtype // empty')
      if [ "$SUBTYPE" = "compact_boundary" ]; then
        echo "" >> "$LOG_FILE"
        echo "[COMPACT] === Context compression ===" >> "$LOG_FILE"
        echo "" >> "$LOG_FILE"
      fi
    fi
  done < "$TRANSCRIPT_PATH"

  # 세션별 hook context 파일 삭제
  if [ -f "$HOOK_CONTEXT_FILE" ]; then
    rm -f "$HOOK_CONTEXT_FILE"
  fi
fi

exit 0