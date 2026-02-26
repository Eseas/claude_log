# Claude Log Organizer 사용 가이드

Claude 대화 로그를 자동으로 분석하고 정리된 마크다운 요약본을 생성하는 시스템입니다.

## 📋 목차

- [설치](#설치)
- [초기 설정](#초기-설정)
- [기본 사용법](#기본-사용법)
- [Interactive 모드 (신규)](#interactive-모드)
- [프롬프트 최적화 (신규)](#프롬프트-최적화)
- [고급 기능](#고급-기능)
- [출력 형식](#출력-형식)
- [문제 해결](#문제-해결)

---

## 설치

### 1. 패키지 설치

```bash
cd /Users/eseas/Desktop/mine/claude_log
pip install -e .
```

### 2. 의존성 확인

```bash
pip list | grep -E "pyyaml|watchdog|jinja2"
```

필요한 패키지:
- `pyyaml>=6.0`
- `watchdog>=3.0.0`
- `jinja2>=3.1.0`
- `python-dateutil>=2.8.0`

---

## 초기 설정

### 1. 설정 파일 생성

```bash
python3 -m claude_log_organizer.cli init
```

이 명령은 `config.yaml` 파일을 생성합니다.

### 2. 설정 파일 편집

`config.yaml`을 열어서 필요한 부분을 수정하세요:

```yaml
watch:
  # 감시할 디렉토리들 (여러 개 지정 가능)
  directories:
    - ./logs
    - /Users/eseas/Documents/project_logs
    - /Users/eseas/Desktop/workspace/micehub-orca/.claude/logs

  # 파일 패턴 (모든 .log 파일)
  patterns:
    - '*.log'

  poll_interval: 1.0
  recursive: false

output:
  # 정리된 파일이 저장될 디렉토리
  directory: ./tasks

  # 출력 파일명 형식
  filename_pattern: task-{task_id}.md
```

### 3. 디렉토리 구조 확인

```bash
# 로그 파일이 저장될 디렉토리
mkdir -p logs

# 정리된 파일이 저장될 디렉토리
mkdir -p tasks
```

---

## 기본 사용법

### 1. Watch 모드 (자동 감시)

**가장 추천하는 방법입니다.** 디렉토리를 실시간으로 감시하고 새 로그가 생기면 자동 처리합니다.

```bash
python3 -m claude_log_organizer.cli watch
```

**출력 예시:**
```
============================================================
Starting Claude Log Organizer in watch mode
============================================================
Watching 3 directories:
  [1] /Users/eseas/Desktop/mine/claude_log/logs
  [2] /Users/eseas/Documents/project_logs
  [3] /Users/eseas/Desktop/workspace/micehub-orca/.claude/logs
Output: /Users/eseas/Desktop/mine/claude_log/tasks
Patterns: ['*.log']
Press Ctrl+C to stop
============================================================
Started watching: /Users/eseas/Desktop/mine/claude_log/logs
Started watching: /Users/eseas/Documents/project_logs
Started watching: /Users/eseas/Desktop/workspace/micehub-orca/.claude/logs
Total directories watching: 3
```

**중지하기:** `Ctrl+C`를 누르세요.

### 2. 단일 파일 처리

특정 로그 파일 하나만 처리하고 싶을 때:

```bash
python3 -m claude_log_organizer.cli process logs/2026-02-12_174649_session-id.log
```

**출력 예시:**
```
[INFO] Processing: logs/2026-02-12_174649_session-id.log
[INFO] Parsing: logs/2026-02-12_174649_session-id.log
[INFO] Generated markdown: tasks/task-session-id.md
[INFO] ✓ Generated: tasks/task-session-id.md
```

### 3. 배치 처리 (여러 파일 한번에)

디렉토리의 모든 로그 파일을 한번에 처리:

```bash
python3 -m claude_log_organizer.cli batch logs/
```

**출력 예시:**
```
[INFO] Scanning directory: logs
[INFO] Patterns: ['*.log']
[INFO] Found 5 matching files
[INFO] [1/5] Processing: conversation-task-abc123.log
[INFO] ✓ Generated: tasks/task-abc123.md
[INFO] [2/5] Processing: 2026-02-12_174649_session-id.log
[INFO] ✓ Generated: tasks/task-session-id.md
...
[INFO] Completed processing 5 files
```

**강제 재처리 (이미 처리된 파일도 다시 처리):**
```bash
python3 -m claude_log_organizer.cli batch logs/ --force
```

### 4. 처리 기록 초기화

이미 처리된 파일 목록을 지우고 싶을 때:

```bash
python3 -m claude_log_organizer.cli clear
```

---

## Interactive 모드

대화형 메뉴를 통해 편리하게 사용할 수 있습니다.

### 시작하기

```bash
python3 -m claude_log_organizer.interactive
```

### 메뉴 구조

```
1. Watch - 디렉토리 모니터링 시작
   → Config에서 디렉토리 사용
   → 직접 입력

2. Request AI - AI 요약 요청 ⭐ 신규
   → 세션 선택 (단일/다중)
   → 분석 타입 선택
      - 일반 요약
      - 효율성 분석 (프롬프트 최적화)
   → AI 방식 선택
      - Claude Code CLI (추천)
      - API 키

3. Exit - 종료
```

### AI 요약 기능

**1단계: 세션 선택**

세션별로 그룹화된 task 파일들을 선택:

```
세션 d7a7214a... (3개 파일, 12.5KB, 2026-02-13 09:48)
세션 84835d73... (2개 파일, 8.3KB, 2026-02-13 09:08)
```

**2단계: 분석 타입 선택**

- **일반 요약**: 세션에서 무슨 일을 했는지 종합 요약
- **효율성 분석**: 프롬프트 효율성 + 개선 제안 (프롬프트 최적화)

**3단계: AI 방식 선택**

- **Claude Code CLI**: settings.local.json 권한으로 안전하게 실행
- **API 키**: Anthropic API 키 사용

### 출력 위치

- **일반 요약**: `summaries/session-{id}_summary.md`
- **효율성 분석**: `summaries/session-{id}_efficiency.md`

---

## 프롬프트 최적화

**목표**: 최소한의 토큰으로 최대한 명확한 지시를 할 수 있도록 학습

### 핵심 개념

```
짧고 불명확한 요청 (❌)
  ↓
여러 번 왕복 (비효율)
  ↓
작은 수정 많음 (직접 하는 게 빠름)

vs

짧지만 명확한 요청 (✅)
  ↓
1-2회 왕복 (효율)
  ↓
작은 수정 적음 (AI가 정확히 이해)
```

### 효율성 분석 출력 예시

```markdown
# Session 효율성 분석: d7a7214a...

## 프롬프트 효율성 분석

### 초기 요청 분석
- **원본 요청**: "파일이 이상해요"
- **포함된 정보**:
  - ❌ 파일명: 없음
  - ❌ 현상: 모호함
  - ❌ 기대결과: 없음
- **토큰 효율성**: 하
- **명확성**: 하
- **왕복 횟수**: 5회 (많음)

### 최적화된 프롬프트 제안

만약 처음부터 이렇게 요청했다면 1회로 완료:

```
event_dispatcher.py:70 _process_with_debounce
현상: created 이벤트 debounce 미적용
기대: modified처럼 3초 대기
```

**개선 포인트**:
- 파일명:라인 명시 → 즉시 위치 파악
- 현상 구체화 → 오해 방지
- 기대결과 명시 → 정확한 수정

### 학습 포인트

**효과적이었던 표현**:
- "event_dispatcher.py 확인"
- "debouncing 로직"

**비효율적이었던 표현**:
- "파일이 이상해요" → 어떤 파일? 어떻게 이상?
- "확인해주세요" → 무엇을 확인?

**다음번 개선 사항**:
1. 파일명:라인 넘버 형식 사용
2. "현상: X, 기대: Y" 구조 사용
3. 참고할 기존 코드 명시
```

### 패턴 학습 프로세스

```
1. 주말에 평일 로그 분석
   → 효율성 분석 실행

2. 효율적/비효율적 패턴 추출
   → prompt_optimizer/patterns/patterns.jsonl에 저장

3. 패턴 데이터베이스 구축
   → 요청 타입별 필수 요소 학습

4. 프롬프트 생성기 개발 (향후)
   → 짧은 입력 → 명확한 프롬프트 자동 생성
```

### 패턴 데이터베이스

저장 위치: `prompt_optimizer/patterns/patterns.jsonl`

```python
from prompt_optimizer.patterns.pattern_db import PatternDB

db = PatternDB()

# 효율적인 패턴 조회
efficient = db.get_efficient_patterns(pattern_type="bug_fix")

# 통계 확인
stats = db.get_statistics()
print(f"평균 왕복: {stats['avg_rounds']}")
print(f"토큰 절약: {stats['avg_token_reduction']}%")
```

### 효율성 메트릭

- **왕복 횟수**: 1-2회 = 최고, 3회 = 보통, 4회+ = 개선 필요
- **토큰 효율성**: (정보량 / 문자수) 비율
- **명확성 점수**: AI 오해 가능성
- **완성도**: 첫 시도 성공률

### 프롬프트 템플릿

효율적인 요청의 기본 구조:

#### 버그 수정
```
파일:라인 함수명
현상: X
기대: Y
[참고: Z]
```

#### 기능 추가
```
위치: 파일:함수
동작: X하면 Y
참고: 기존 Z 패턴
```

#### 리팩토링
```
대상: 파일:라인-라인
방식: X로 변경
제약: Y 유지
```

---

## 고급 기능

### 여러 디렉토리 동시 감시

`config.yaml`에 여러 디렉토리를 추가하면 모두 동시에 감시합니다:

```yaml
watch:
  directories:
    - /Users/eseas/Desktop/mine/claude_log/logs
    - /Users/eseas/Documents/project_logs
    - /Users/eseas/Desktop/workspace/micehub-orca/.claude/logs
    - /Volumes/ExternalDrive/backup_logs
```

### 커스텀 설정 파일 사용

다른 설정 파일을 사용하고 싶을 때:

```bash
python3 -m claude_log_organizer.cli watch -c custom_config.yaml
python3 -m claude_log_organizer.cli process file.log -c custom_config.yaml
```

### 하위 디렉토리 포함

하위 디렉토리의 로그 파일도 감시하려면:

```yaml
watch:
  recursive: true
```

### 파일 패턴 커스터마이징

특정 패턴의 파일만 처리하려면:

```yaml
watch:
  patterns:
    - 'conversation-*.log'
    - '2026-*-*.log'
    - 'session-*.log'
```

---

## 출력 형식

### 생성되는 마크다운 파일 구조

```markdown
# Task Summary: session-id

**Status**: ✅ Completed
**Timestamp**: 2026-02-12 17:46:49
---

## Summary

**초기 요청**: 방금 커밋한 내용 정리해봐

**수행 작업**:
- Bash 2회 사용
- Read 사용
- Edit 사용

**결과**: 수정 완료했습니다.

---

## Implementation Details

### Files Modified
- `/path/to/file1.py`
- `/path/to/file2.java`

### Files Created
- `/path/to/newfile.sh`

### Key Technical Decisions
- 보고서 조회 방식을 단일 쿼리로 통합
- corpIdxWriter 기준으로 변경
- hook 스크립트 디버깅 코드 추가

---

*Generated by Claude Log Organizer*
```

### 지원하는 로그 형식

#### 1. Claude Code 세션 로그
```
=== Claude Code Session Log ===
Session ID: bfd53305-f09a-45e4-9b4c-6dee8e23d9b1
Project: /path/to/project
Saved at: 2026-02-12 17:46:49
================================

[USER] 질문
[TOOL] ToolName → command
[ASSISTANT] 응답
```

**파일명 형식**: `YYYY-MM-DD_HHMMSS_session-id.log`

#### 2. 일반 Conversation 로그

일반적인 대화 로그 형식도 지원합니다.

**파일명 형식**: `conversation-task-*.log`

#### 3. Timeline 로그

Phase 정보가 있는 타임라인 로그:
```
[2026-02-12T13:06:24.310645] [PHASE] validation_start
[2026-02-12T13:06:24.402471] [PHASE] validation_done
```

**파일명 형식**: `timeline.log`, `*timeline*.log`

---

## 실전 사용 예시

### 시나리오 1: Claude Code Hook과 연동

**1단계: Hook 설정**

Claude Code의 Stop hook에서 로그 저장 스크립트 실행:

```bash
# ~/.claude/hooks/save-conversation-log.sh
# 대화가 끝날 때마다 로그 저장
```

**2단계: Watch 모드 실행**

```bash
cd /Users/eseas/Desktop/mine/claude_log
python3 -m claude_log_organizer.cli watch
```

**3단계: 자동 처리**

Claude Code에서 작업하면 로그가 자동으로:
1. Hook이 로그 파일 생성 → `~/workspace/project/.claude/logs/`
2. Watch 모드가 감지 → 자동 파싱
3. 정리된 마크다운 생성 → `./tasks/`

### 시나리오 2: 과거 로그 일괄 정리

여러 프로젝트의 과거 로그를 한번에 정리:

```bash
# 1. 여러 디렉토리 설정
vim config.yaml
# directories에 모든 프로젝트 로그 경로 추가

# 2. 일괄 처리
python3 -m claude_log_organizer.cli batch ~/Desktop/workspace/project1/.claude/logs/
python3 -m claude_log_organizer.cli batch ~/Desktop/workspace/project2/.claude/logs/
python3 -m claude_log_organizer.cli batch ~/Documents/logs/
```

### 시나리오 3: 특정 세션만 선택적으로 정리

```bash
# 특정 날짜의 로그만 처리
python3 -m claude_log_organizer.cli process logs/2026-02-12_*.log

# 특정 세션 ID만 처리
python3 -m claude_log_organizer.cli process logs/*bfd53305*.log
```

---

## 중복 처리 방지

### 자동 중복 방지

시스템은 파일의 **SHA256 해시**를 사용하여 중복 처리를 방지합니다.

**처리 기록 파일**: `.processed.json`

```json
{
  "/path/to/file.log": {
    "hash": "56d5fcca4da09ed5724608b562941a32dd375650e8a73ed079d1c39a79a238ac",
    "processed_at": "2026-02-12T17:51:12.510411",
    "size": 2233
  }
}
```

### 동작 방식

1. **파일이 처음 처리될 때**: 해시를 계산하고 `.processed.json`에 저장
2. **같은 파일을 다시 처리할 때**: 해시가 같으면 건너뜀
3. **파일 내용이 변경되면**: 해시가 달라지므로 다시 처리

### 강제 재처리

```bash
# 방법 1: 처리 기록 초기화
python3 -m claude_log_organizer.cli clear

# 방법 2: --force 옵션 사용
python3 -m claude_log_organizer.cli batch logs/ --force
```

---

## 문제 해결

### 문제: 파일이 처리되지 않음

**원인 확인:**
```bash
# 1. 로그 파일 확인
tail -f organizer.log

# 2. 파일 패턴 확인
ls -la logs/*.log

# 3. 처리 기록 확인
cat .processed.json
```

**해결 방법:**

1. **파일 패턴이 맞지 않는 경우**
   ```yaml
   # config.yaml
   patterns:
     - '*.log'  # 모든 .log 파일
   ```

2. **이미 처리된 파일인 경우**
   ```bash
   python3 -m claude_log_organizer.cli clear
   ```

3. **파일 크기 문제**
   - 너무 작은 파일 (< 10 bytes): 무시됨
   - 너무 큰 파일 (> 100 MB): 무시됨

### 문제: Watch 모드가 파일을 감지하지 못함

**확인 사항:**

1. **디렉토리 경로가 올바른지 확인**
   ```yaml
   # 절대 경로 사용 권장
   directories:
     - /Users/eseas/Desktop/mine/claude_log/logs
   ```

2. **권한 확인**
   ```bash
   ls -la /path/to/watch/directory
   ```

3. **파일이 실제로 생성되는지 확인**
   ```bash
   # 다른 터미널에서
   touch logs/test.log
   # Watch 모드 로그 확인
   ```

### 문제: 출력 파일이 생성되지 않음

**확인 사항:**

1. **출력 디렉토리가 존재하는지**
   ```bash
   mkdir -p tasks
   ```

2. **덮어쓰기 설정 확인**
   ```yaml
   output:
     overwrite: false  # true로 변경하면 항상 덮어씀
   ```

3. **템플릿 파일 확인**
   ```bash
   ls -la templates/default.md.jinja2
   ```

### 문제: 로그에 에러 메시지가 보임

**로그 확인:**
```bash
tail -f organizer.log
```

**일반적인 에러:**

1. **ParsingError**: 로그 파일 형식이 예상과 다름
   - 파일 내용 확인
   - 올바른 형식인지 검증

2. **IOError**: 파일 읽기 권한 없음
   - 파일 권한 확인: `chmod 644 logs/*.log`

3. **Template Error**: Jinja2 템플릿 오류
   - 템플릿 파일 확인
   - 문법 오류 수정

---

## 로그 레벨 조정

디버깅을 위해 로그 레벨을 변경:

```yaml
# config.yaml
logging:
  level: DEBUG  # INFO, WARNING, ERROR, CRITICAL
  file: organizer.log
```

상세한 로그 확인:
```bash
tail -f organizer.log | grep -E "DEBUG|ERROR"
```

---

## 성능 최적화

### 대량의 로그 파일 처리

```bash
# 배치 처리가 더 빠름
python3 -m claude_log_organizer.cli batch logs/

# 보다는
# watch 모드에서 하나씩 처리되는 것이 더 느림
```

### 여러 디렉토리 감시 시

- **권장**: 5개 이하의 디렉토리
- **최대**: 10개 정도까지 안정적
- 너무 많으면 시스템 리소스 사용량 증가

### 파일 크기 제한

기본 제한:
- 최소: 10 bytes
- 최대: 100 MB

변경하려면 `event_dispatcher.py`의 `_validate_file()` 메서드 수정

---

## 추가 자료

- [README.md](README.md) - 프로젝트 개요 및 기본 정보
- [MULTIPLE_DIRECTORIES.md](MULTIPLE_DIRECTORIES.md) - 여러 디렉토리 감시 상세 가이드
- [config.yaml.example](config.yaml.example) - 전체 설정 옵션 예시

---

## 도움말

### 명령어 도움말 보기

```bash
python3 -m claude_log_organizer.cli --help
python3 -m claude_log_organizer.cli watch --help
python3 -m claude_log_organizer.cli process --help
python3 -m claude_log_organizer.cli batch --help
```

### 빠른 참조

| 작업 | 명령어 |
|------|--------|
| 설정 생성 | `claude-log-organizer init` |
| 자동 감시 | `claude-log-organizer watch` |
| 파일 처리 | `claude-log-organizer process <file>` |
| 배치 처리 | `claude-log-organizer batch <dir>` |
| 기록 초기화 | `claude-log-organizer clear` |

---
