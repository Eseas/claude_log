# 여러 디렉토리 감시 기능 사용 가이드

Claude Log Organizer가 여러 디렉토리를 동시에 감시할 수 있도록 업데이트되었습니다.

## 주요 변경사항

### 1. 설정 파일 형식 변경

**기존 (단일 디렉토리):**
```yaml
watch:
  directory: ./logs
```

**신규 (여러 디렉토리):**
```yaml
watch:
  directories:
    - ./logs
    - /Users/username/Documents/project_logs
    - /Users/username/Desktop/work_logs
```

## 설정 방법

### config.yaml 수정

```yaml
watch:
  # 감시할 디렉토리들 (절대 경로 또는 상대 경로)
  directories:
    - ./logs
    - /Users/eseas/Documents/claude_conversations
    - /Users/eseas/Desktop/project_logs
    - /Volumes/ExternalDrive/backup_logs

  # 모든 디렉토리에 공통으로 적용되는 파일 패턴
  patterns:
    - "conversation-task-*.log"
    - "task-*.log"

  poll_interval: 1.0
  recursive: false
```

### 지원되는 경로 형식

1. **상대 경로**: `./logs`, `../other_logs`
2. **절대 경로**: `/Users/username/Documents/logs`
3. **홈 디렉토리**: `~/Documents/logs` (자동으로 절대 경로로 변환됨)
4. **외장 드라이브**: `/Volumes/ExternalDrive/logs`

## 사용 예시

### 1. Watch 모드 (여러 디렉토리 동시 감시)

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
  [3] /Volumes/ExternalDrive/backup_logs
Output: /Users/eseas/Desktop/mine/claude_log/tasks
Patterns: ['conversation-task-*.log']
Press Ctrl+C to stop
============================================================
Started watching: /Users/eseas/Desktop/mine/claude_log/logs
Started watching: /Users/eseas/Documents/project_logs
Started watching: /Volumes/ExternalDrive/backup_logs
Total directories watching: 3
```

### 2. 특정 디렉토리만 배치 처리

```bash
# 첫 번째 디렉토리만 처리
python3 -m claude_log_organizer.cli batch /Users/eseas/Desktop/mine/claude_log/logs

# 두 번째 디렉토리만 처리
python3 -m claude_log_organizer.cli batch /Users/eseas/Documents/project_logs
```

### 3. 단일 파일 처리

```bash
# 어떤 디렉토리에 있는 파일이든 처리 가능
python3 -m claude_log_organizer.cli process /Users/eseas/Documents/project_logs/conversation-task-abc123.log
```

## 하위 호환성

기존 설정 파일도 계속 작동합니다:

```yaml
# 이전 방식 (여전히 지원됨)
watch:
  directory: ./logs
```

내부적으로 자동으로 리스트 형태로 변환되어 처리됩니다.

## 실제 사용 시나리오

### 시나리오 1: 여러 프로젝트 로그 관리

```yaml
watch:
  directories:
    - /Users/eseas/Documents/project_A/logs
    - /Users/eseas/Documents/project_B/logs
    - /Users/eseas/Documents/project_C/logs
  patterns:
    - "conversation-*.log"
```

### 시나리오 2: 로컬 + 클라우드 동기화 폴더

```yaml
watch:
  directories:
    - ./logs                                    # 로컬
    - ~/Dropbox/claude_logs                     # Dropbox
    - ~/Google Drive/My Drive/work_logs         # Google Drive
  patterns:
    - "conversation-task-*.log"
```

### 시나리오 3: 여러 사용자 환경

```yaml
watch:
  directories:
    - /Users/eseas/Desktop/mine/claude_log/logs
    - /Users/eseas/Downloads                    # 다운로드 폴더
    - /Volumes/ExternalDrive/backup_logs        # 외장 드라이브
  patterns:
    - "*.log"
  recursive: true  # 하위 폴더도 감시
```

## 주의사항

### 1. 디렉토리가 없는 경우

- 설정에 지정된 디렉토리가 없으면 **자동으로 생성**됩니다
- 로그에 생성 메시지가 표시됩니다: `Created watch directory: /path/to/dir`

### 2. 권한 문제

- 각 디렉토리에 대한 **읽기 권한**이 필요합니다
- 권한이 없는 디렉토리는 에러 로그와 함께 건너뜁니다

### 3. 성능 고려사항

- 너무 많은 디렉토리(10개 이상)를 감시하면 시스템 리소스를 많이 사용할 수 있습니다
- 각 디렉토리마다 별도의 watchdog observer가 실행됩니다
- 필요한 디렉토리만 설정하는 것을 권장합니다

### 4. 외장 드라이브

- 외장 드라이브가 마운트되지 않은 상태에서 시작하면 디렉토리가 생성되지 않습니다
- 외장 드라이브를 연결한 후 프로그램을 재시작해야 합니다

## 테스트

### 설정이 올바른지 확인

```bash
# 1. Watch 모드 시작
python3 -m claude_log_organizer.cli watch

# 2. 다른 터미널에서 테스트 파일 생성
echo "test" > /path/to/watched/directory/conversation-task-test.log

# 3. 로그 확인
tail -f organizer.log

# 예상 출력:
# [INFO] New file detected: /path/to/watched/directory/conversation-task-test.log
# [INFO] Parsing: /path/to/watched/directory/conversation-task-test.log
# [INFO] ✓ Generated: tasks/task-test.md
```

## 문제 해결

### 디렉토리가 감시되지 않는 경우

1. **경로 확인**: 절대 경로로 작성했는지 확인
   ```yaml
   # 잘못된 예
   directories:
     - ~/Documents/logs  # 틸다(~)는 지원되지 않을 수 있음

   # 올바른 예
   directories:
     - /Users/eseas/Documents/logs
   ```

2. **권한 확인**:
   ```bash
   ls -la /path/to/directory
   ```

3. **로그 확인**:
   ```bash
   tail -f organizer.log
   ```

### 파일이 처리되지 않는 경우

1. **패턴 확인**: 파일 이름이 설정된 패턴과 일치하는지 확인
2. **중복 확인**: `.processed.json` 파일에서 이미 처리된 파일인지 확인
3. **파일 크기**: 너무 작거나(< 10 bytes) 큰(> 100MB) 파일은 건너뜁니다

## 추가 정보

- 모든 디렉토리는 **독립적으로** 감시됩니다
- 각 디렉토리의 파일 변경사항이 **실시간으로** 감지됩니다
- 출력 디렉토리는 하나만 설정 가능합니다 (`output.directory`)
- 처리된 파일은 디렉토리 위치와 관계없이 **하나의 tracker**에서 관리됩니다
