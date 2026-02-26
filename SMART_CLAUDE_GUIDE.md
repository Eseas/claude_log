# Smart Claude 가이드

AI 프롬프트를 자동으로 최적화하여 Claude Code에 전달하는 도구입니다.

## 🎯 목표

```
기존: "debouncing 버그" → Claude → 5번 왕복

Smart Claude: "debouncing 버그"
              → 자동 최적화: "event_dispatcher.py:70
                              현상: created 이벤트 debounce 미적용
                              기대: modified처럼 3초 대기"
              → Claude → 1-2번 왕복
```

## 📦 설치

### 1. 별칭 설치

```bash
cd /Users/eseas/Desktop/mine/claude_log
./scripts/install-alias.sh
source ~/.zshrc  # 또는 ~/.bashrc
```

### 2. 수동 설정

`.zshrc` 또는 `.bashrc`에 추가:

```bash
alias smart-claude='/Users/eseas/Desktop/mine/claude_log/scripts/smart-claude.sh'
```

## 🚀 사용법

### 기본 사용

```bash
smart-claude "debouncing 버그"
```

**동작:**
1. 프롬프트 자동 최적화
2. Claude Code 호출
3. 결과 출력

### Interactive 모드 (추천)

```bash
smart-claude --interactive "파일 이상해"
```

**동작:**
1. 프롬프트 최적화
2. **최적화 결과 확인**
3. 확인 후 Claude 호출

**출력 예시:**
```
[프롬프트 최적화 중...]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
보강된 프롬프트:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
event_dispatcher.py:70
현상: 파일 이상해
기대: 정상 동작

---
### 원본 요청
파일 이상해
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

이 프롬프트로 Claude를 호출하시겠습니까? (y/N):
```

### Dry Run (최적화만)

```bash
smart-claude --dry-run "에러 확인"
```

최적화된 프롬프트만 보고, Claude는 호출하지 않음.

### 최적화 건너뛰기

```bash
smart-claude --no-optimize "이미 최적화된 프롬프트"
```

## 🎨 최적화 예시

### 버그 수정

**입력:**
```bash
smart-claude "debouncing 안됨"
```

**최적화:**
```
event_dispatcher.py:70
현상: debouncing 안됨
기대: 정상 동작
에러: [2026-02-13] ERROR File not processed

---
### 원본 요청
debouncing 안됨
```

### 기능 추가

**입력:**
```bash
smart-claude "효율성 분석 추가"
```

**최적화:**
```
위치: interactive.py
동작: 효율성 분석 추가
참고: session_analyzer.py 패턴

---
### 원본 요청
효율성 분석 추가
```

### 코드 조사

**입력:**
```bash
smart-claude "승인 워크플로우 확인"
```

**최적화:**
```
목적: 승인 워크플로우 확인
범위: corp-report/[meetingIdx].vue
질문: 승인 워크플로우 확인

---
### 원본 요청
승인 워크플로우 확인
```

## 🔧 작동 원리

### 1. 문맥 파악
```python
# 최근 수정 파일
git log --name-only -n 10

# 현재 수정 중인 파일
git status --short

# 마지막 에러
tail organizer.log
```

### 2. 키워드 추출
```
"debouncing 버그" → ["debouncing", "버그"]
```

### 3. 파일 추론
```
"debouncing" → event_dispatcher.py (최근 수정 파일 중 매칭)
```

### 4. 함수/라인 추론
```
event_dispatcher.py에서 "debounce" 검색 → 70번 라인
```

### 5. 템플릿 적용
```
버그 키워드 감지 → 버그 수정 템플릿:
  파일:라인
  현상: X
  기대: Y
```

### 6. 원본 포함
```
최적화 프롬프트
---
### 원본 요청
사용자 입력
```

## 🎯 품질 점수

최적화 품질을 0-100%로 계산:

- ✅ 파일:라인 형식 (+30%)
- ✅ "현상:" 포함 (+20%)
- ✅ "기대:" 포함 (+20%)
- ✅ 함수명 포함 (+30%)

**예시:**
- `event_dispatcher.py:70` → 30%
- `+ 현상: X 안됨` → 50%
- `+ 기대: Y` → 70%
- `+ def _process_with_debounce` → 100%

## 📊 옵션 요약

| 옵션 | 설명 | 사용 예 |
|------|------|---------|
| (기본) | 자동 최적화 + Claude 호출 | `smart-claude "버그"` |
| `-i, --interactive` | 최적화 확인 후 호출 | `smart-claude -i "버그"` |
| `-d, --dry-run` | 최적화만 (Claude 호출 안함) | `smart-claude -d "버그"` |
| `-n, --no-optimize` | 최적화 건너뛰기 | `smart-claude -n "이미 최적화됨"` |

## 🔄 워크플로우

### 개발 중

```bash
# 간단히 물어보기
smart-claude "이 파일 확인"

# → 자동 최적화
# → 빠른 답변
```

### 복잡한 요청

```bash
# 확인하면서 진행
smart-claude --interactive "기능 추가"

# → 최적화 결과 확인
# → 괜찮으면 y
# → Claude 호출
```

### 테스트

```bash
# 최적화만 테스트
smart-claude --dry-run "테스트 입력"

# → 최적화 결과만 확인
# → Claude 호출 안함
```

## 🚀 고급 사용법

### 파이프라인

```bash
# 최적화만
smart-claude --dry-run "버그" > optimized.txt

# 나중에 사용
cat optimized.txt | claude --print
```

### 스크립트에서 사용

```bash
#!/bin/bash

TASKS=("버그 수정" "기능 추가" "코드 조사")

for task in "${TASKS[@]}"; do
    echo "처리 중: $task"
    smart-claude --interactive "$task"
done
```

### 별칭 추가

```bash
# ~/.zshrc
alias sc='smart-claude'
alias sci='smart-claude --interactive'
alias scd='smart-claude --dry-run'

# 사용
sc "버그"
sci "기능 추가"
scd "테스트"
```

## 🎓 학습 효과

### 1주차
```
smart-claude "버그"
→ 최적화 확인
→ 어떻게 변환되는지 학습
```

### 2주차
```
최적화 패턴 이해
→ 직접 명확하게 작성 시작
→ --no-optimize 사용 증가
```

### 1개월 후
```
자동으로 명확한 프롬프트 작성
→ smart-claude 거의 불필요
→ 목표 달성!
```

## 🔍 문제 해결

### "claude: command not found"

```bash
# Claude Code CLI 설치 확인
which claude

# 없으면 설치
# https://claude.ai/download
```

### "최적화 실패"

```bash
# 수동으로 테스트
python3 prompt_optimizer/cli.py optimize "테스트"

# 에러 확인
python3 -c "from prompt_optimizer.generator import PromptGenerator"
```

### "git: command not found"

프로젝트가 git 저장소가 아니면 문맥 파악 제한됨.
기본 최적화는 여전히 작동.

## 📚 관련 문서

- [PROMPT_OPTIMIZATION.md](PROMPT_OPTIMIZATION.md) - 최적화 원리
- [USAGE_GUIDE.md](USAGE_GUIDE.md) - 전체 시스템 가이드

---

**핵심**: Interactive 모드(`-i`)로 시작하여 최적화 패턴을 학습하세요!
