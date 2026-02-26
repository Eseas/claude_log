#!/bin/bash
# Auto-optimize Claude - claude 명령어를 자동으로 최적화하는 버전으로 대체
#
# 설치:
#   source scripts/auto-optimize.sh
#   또는 ~/.zshrc에 추가

# 원본 claude 경로 저장
ORIGINAL_CLAUDE=$(which claude)

if [ -z "$ORIGINAL_CLAUDE" ]; then
    echo "에러: Claude Code CLI를 찾을 수 없습니다."
    return 1
fi

# 프로젝트 경로
OPTIMIZER_ROOT="/Users/eseas/Desktop/mine/claude_log"

# claude 함수 정의 (명령어 오버라이드)
claude() {
    # 옵션 파싱
    local AUTO_OPTIMIZE=true
    local INTERACTIVE=false
    local args=()

    while [[ $# -gt 0 ]]; do
        case $1 in
            --no-optimize)
                AUTO_OPTIMIZE=false
                shift
                ;;
            --optimize-interactive)
                INTERACTIVE=true
                shift
                ;;
            *)
                args+=("$1")
                shift
                ;;
        esac
    done

    # 인자가 있고 최적화가 활성화된 경우
    if [ ${#args[@]} -gt 0 ] && [ "$AUTO_OPTIMIZE" = true ]; then
        local user_input="${args[*]}"

        # 최적화 실행
        local optimized
        if optimized=$(python3 "$OPTIMIZER_ROOT/prompt_optimizer/cli.py" optimize --quiet "$user_input" 2>/dev/null); then

            # Interactive 모드
            if [ "$INTERACTIVE" = true ]; then
                echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                echo "원본: $user_input"
                echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                echo "$optimized"
                echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                read -p "이 프롬프트로 진행하시겠습니까? (y/N): " -n 1 -r
                echo
                if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                    echo "취소되었습니다."
                    return 0
                fi
            else
                # 자동 모드: 조용히 최적화만
                echo "[자동 최적화됨]"
            fi

            # 최적화된 프롬프트로 실행
            echo "$optimized" | $ORIGINAL_CLAUDE "${args[@]}"
        else
            # 최적화 실패 시 원본 사용
            $ORIGINAL_CLAUDE "${args[@]}"
        fi
    else
        # 최적화 없이 원본 실행
        $ORIGINAL_CLAUDE "${args[@]}"
    fi
}

# Export function
export -f claude

echo "✓ Claude 자동 최적화 활성화됨"
echo ""
echo "사용법:"
echo "  claude \"버그 수정\"              # 자동 최적화"
echo "  claude --optimize-interactive \"버그\"  # 확인 후 진행"
echo "  claude --no-optimize \"원본 그대로\"     # 최적화 건너뛰기"
echo ""
echo "비활성화:"
echo "  unset -f claude"
