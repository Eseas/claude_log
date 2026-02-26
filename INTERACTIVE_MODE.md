# 인터랙티브 모드 사용 가이드

Claude Log Organizer의 인터랙티브 메뉴 시스템을 사용하는 방법입니다.

## 실행 방법

### 기본 실행

```bash
python3 -m claude_log_organizer.interactive
```

또는 패키지 설치 후:

```bash
claude-log-organizer-interactive
```

## 메뉴 구조

### 메인 메뉴

```
Claude Log Organizer - Interactive Mode
============================================================

작업을 선택하세요:
  1. Watch - 디렉토리 모니터링 시작
  2. Request AI - AI 요약 요청
  3. Exit - 종료
```

---

## 1. Watch - 디렉토리 모니터링

로그 파일이 생성되는 디렉토리를 실시간으로 감시합니다.

### 하위 메뉴

```
디렉토리 선택 방법:
  1. Config - 설정 파일의 디렉토리 사용
  2. Manual - 직접 입력
  3. Back - 메인 메뉴로 돌아가기
```

### 1-1. Config 방식

`config.yaml`에 설정된 디렉토리를 사용합니다.

**예시:**
```
📂 설정된 디렉토리:
  1. /Users/eseas/Desktop/mine/claude_log/logs
  2. /Users/eseas/Documents/project_logs
  3. /Users/eseas/Desktop/workspace/micehub-orca/.claude/logs

⏳ 모니터링을 시작합니다...
   (Ctrl+C를 눌러 중지)

Started watching: /Users/eseas/Desktop/mine/claude_log/logs
Started watching: /Users/eseas/Documents/project_logs
Started watching: /Users/eseas/Desktop/workspace/micehub-orca/.claude/logs
Total directories watching: 3
```

### 1-2. Manual 방식

디렉토리를 직접 입력합니다. 빈 값을 입력하면 완료됩니다.

**예시:**
```
📝 모니터링할 디렉토리를 입력하세요
   (빈 값을 입력하면 완료)

디렉토리 1: ~/Documents/logs
✓ 추가됨: /Users/eseas/Documents/logs

디렉토리 2: ~/Desktop/project_logs
✓ 추가됨: /Users/eseas/Desktop/project_logs

디렉토리 3:
(엔터 - 완료)

📂 선택된 디렉토리:
  1. /Users/eseas/Documents/logs
  2. /Users/eseas/Desktop/project_logs

⏳ 모니터링을 시작합니다...
```

**주의사항:**
- 디렉토리가 존재하지 않으면 생성 여부를 묻습니다
- 최소 1개 이상의 디렉토리를 입력해야 합니다
- 상대 경로와 절대 경로 모두 사용 가능
- `~`는 자동으로 홈 디렉토리로 확장됩니다

### 중지 방법

모니터링 중 `Ctrl+C`를 누르면 중지되고 메인 메뉴로 돌아갑니다.

---

## 2. Request AI - AI 요약 요청

이미 생성된 task 파일들을 선택하여 AI 요약을 요청합니다.

### 파일 선택 화면

```
AI 요약을 요청할 파일을 선택하세요 (Space로 선택, Enter로 확인)
  [ ] [ All ] - 모든 파일 선택
  [ ] task-bfd53305-f09a-45e4-9b4c-6dee8e23d9b1.md (3.7KB)
  [ ] task-145358.md (3.6KB)
  [ ] task-140008.md (3.7KB)
  [ ] task-test123.md (3.6KB)
  [ ] [ Cancel ] - 취소
```

### 조작 방법

- **↑/↓ 화살표**: 항목 이동
- **Space**: 선택/해제
- **Enter**: 확인
- **Ctrl+C**: 취소

### 특수 선택지

- **[ All ]**: 모든 파일을 한번에 선택
- **[ Cancel ]**: 취소하고 메인 메뉴로 돌아가기

### API 키 입력

처음 실행 시 Claude API 키를 입력해야 합니다.

```
🔑 Claude API 키가 필요합니다.
   https://console.anthropic.com/account/keys 에서 발급받으세요.

API Key: sk-ant-api03-...

이 API 키를 config.yaml에 저장하시겠습니까? (y/N): y
✓ 저장되었습니다.
```

**API 키 발급 방법:**
1. https://console.anthropic.com/account/keys 방문
2. "Create Key" 클릭
3. 생성된 키 복사
4. 프로그램에 붙여넣기

**저장 여부:**
- `y` 입력: `config.yaml`에 저장됨 (다음부터 자동 사용)
- `N` 입력: 이번만 사용 (다음에 다시 입력 필요)

### AI 요약 진행

```
✓ 3개 파일 선택됨

⏳ 3개 파일을 AI로 요약 중...

[1/3] task-bfd53305-f09a-45e4-9b4c-6dee8e23d9b1.md
  ✓ 요약 완료: task-bfd53305-f09a-45e4-9b4c-6dee8e23d9b1_summary.md

[2/3] task-145358.md
  ✓ 요약 완료: task-145358_summary.md

[3/3] task-140008.md
  ✓ 요약 완료: task-140008_summary.md

✓ 완료! 3개 파일 요약 생성됨
```

### 요약 파일 형식

생성되는 요약 파일 (`*_summary.md`):

```markdown
# AI 요약: task-bfd53305-f09a-45e4-9b4c-6dee8e23d9b1

## 주요 작업 내용

이 세션에서는 MiceHub-Orca 프로젝트의 보고서 조회 방식을 개선하고,
Claude Code의 대화 로그 저장 hook 스크립트를 디버깅했습니다.

## 수정/생성된 주요 파일

- `/Users/eseas/Desktop/workspace/micehub-orca/src/main/java/.../ReportService.java`
- `/Users/eseas/.claude/hooks/save-conversation-log.sh`

## 핵심 기술적 결정사항

1. **보고서 조회 방식 통합**: External/Internal 분기를 제거하고 `corpIdxWriter` 기준 단일 쿼리로 통합
2. **Hook 스크립트 수정**: transcript JSONL 구조 차이로 인한 파싱 오류 해결
3. **로그 파일명 형식 변경**: 시간 포함에서 날짜만 포함하도록 변경

---

원본 파일: [task-bfd53305-f09a-45e4-9b4c-6dee8e23d9b1.md](task-bfd53305-f09a-45e4-9b4c-6dee8e23d9b1.md)
```

### 요약 내용

AI 요약에는 다음이 포함됩니다:

1. **주요 작업 내용** (2-3문장)
2. **수정/생성된 주요 파일 목록**
3. **핵심 기술적 결정사항**

---

## 3. Exit - 종료

프로그램을 종료하고 터미널로 돌아갑니다.

```
👋 종료합니다.
```

---

## 설정 파일 (config.yaml)

AI 기능 사용을 위해 `config.yaml`에 다음을 추가할 수 있습니다:

```yaml
# AI summarization settings (optional)
ai:
  # Claude API key
  api_key: "sk-ant-api03-..."

  # Model to use
  model: "claude-3-5-sonnet-20241022"

  # Maximum tokens
  max_tokens: 2048
```

**설정하면:**
- API 키를 매번 입력할 필요 없음
- 모델과 토큰 수 커스터마이징 가능

**설정하지 않으면:**
- 첫 사용 시 API 키 입력 프롬프트 표시
- 기본 모델 사용

---

## 문제 해결

### inquirer 패키지 설치 오류

```bash
pip install inquirer
```

### anthropic 패키지 설치 오류

```bash
pip install anthropic
```

### API 키 오류

```
❌ API 키가 유효하지 않습니다.
```

**해결:**
1. https://console.anthropic.com/account/keys에서 새 키 발급
2. 키를 올바르게 복사했는지 확인
3. `config.yaml`의 `ai.api_key`를 확인

### 요약 파일이 생성되지 않음

```
❌ /path/to/tasks에 task 파일이 없습니다.
   먼저 로그를 처리하세요.
```

**해결:**
1. 먼저 Watch 모드로 로그를 처리
2. 또는 CLI로 수동 처리:
   ```bash
   python3 -m claude_log_organizer.cli batch logs/
   ```

---

## 비용 안내

### Claude API 사용 비용

AI 요약 기능은 Claude API를 사용하므로 비용이 발생합니다.

**예상 비용** (Claude 3.5 Sonnet 기준):
- 입력: $3 / 1M tokens
- 출력: $15 / 1M tokens

**실제 사용량 예시:**
- 로그 파일 1개 (3KB): 약 1,000 tokens
- 요약 1개: 약 500 tokens
- **파일 1개당 약 $0.01** (1센트)

**절약 팁:**
- 필요한 파일만 선택
- [ All ] 대신 개별 선택
- 긴 로그는 미리 확인 후 선택

---

## 사용 예시

### 시나리오 1: 매일 작업 로그 요약

```bash
# 1. 인터랙티브 모드 실행
python3 -m claude_log_organizer.interactive

# 2. Watch 선택 → Config 선택
# 3. 하루 종일 모니터링 (백그라운드)
# 4. 저녁에 Ctrl+C로 중지
# 5. Request AI 선택 → [ All ] 선택
# 6. 하루 작업 요약 확인
```

### 시나리오 2: 특정 프로젝트만 요약

```bash
# 1. Watch → Manual 입력
디렉토리 1: ~/workspace/project-a/.claude/logs
디렉토리 2: (빈값 - 완료)

# 2. 작업 완료 후 Ctrl+C
# 3. Request AI → 원하는 파일만 선택
# 4. 프로젝트별 요약 확인
```

### 시나리오 3: API 키 없이 사용

```bash
# Watch 기능만 사용 (무료)
python3 -m claude_log_organizer.interactive
# → Watch 선택
# → 구조화된 마크다운만 생성
# → AI 요약은 건너뛰기
```

---

## 추가 정보

- [USAGE_GUIDE.md](USAGE_GUIDE.md) - 일반 사용법
- [README.md](README.md) - 프로젝트 개요
- [MULTIPLE_DIRECTORIES.md](MULTIPLE_DIRECTORIES.md) - 여러 디렉토리 감시
