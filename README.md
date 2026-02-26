# Claude Log Organizer

Claude Code 대화 로그를 자동으로 수집하고, 구조화된 마크다운 요약 및 draw.io 타임라인 다이어그램을 생성하는 시스템.

## 동작 방식

```
Claude Code 대화
       │
       ▼
┌─────────────────────┐     ┌────────────────────┐
│  JSONL Transcript    │────▶│  save-conversation  │
│  (.claude/projects/) │     │  -log.sh (Stop Hook)│
└─────────────────────┘     └────────┬───────────┘
                                     │
                                     ▼
                            ┌────────────────────┐
                            │  .log 파일           │
                            │  (.claude/logs/)     │
                            └────────┬───────────┘
                                     │
                      ┌──────────────┼──────────────┐
                      ▼              ▼              ▼
              ┌──────────────┐ ┌──────────┐ ┌──────────────┐
              │ session_parser│ │ markdown │ │ timeline     │
              │              │ │ generator│ │ _diagram     │
              └──────┬───────┘ └────┬─────┘ └──────┬───────┘
                     ▼              ▼              ▼
              ┌──────────────┐ ┌──────────┐ ┌──────────────┐
              │ task-*.md    │ │ Jinja2   │ │ .drawio +    │
              │ (tasks/)     │ │ template │ │ companion .md│
              └──────────────┘ └──────────┘ │ (summaries/) │
                                            └──────────────┘
```

### 파이프라인 요약

1. **JSONL 수집** — Claude Code가 대화마다 자동 생성하는 JSONL 트랜스크립트
2. **Hook 변환** — `save-conversation-log.sh`(Stop Hook)가 JSONL을 태그 기반 `.log` 파일로 변환
3. **파싱** — `session_parser.py`가 `.log`를 파싱하여 `TaskData` 모델로 변환
4. **출력 생성** — 마크다운 요약 (`task-*.md`) 및 타임라인 다이어그램 (`.drawio` + companion `.md`)

## 추출 태그

`.log` 파일에 기록되는 태그 목록:

| 태그 | 출처 | 설명 |
|------|------|------|
| `[USER]` | user message | 사용자 입력 텍스트 |
| `[ASSISTANT]` | assistant message | 어시스턴트 응답 텍스트 |
| `[TOOL]` | assistant message | 도구 호출 (이름 + 주요 파라미터) |
| `[THINKING]` | assistant message | 사고 과정 (thinking block) |
| `[TOOL_RESULT]` | user message | 도구 실행 결과 (300자 제한) |
| `[DOCUMENT]` | user message | 첨부 문서 제목 |
| `[SNAPSHOT]` | file-history-snapshot | 파일 수정 스냅샷 (추적 파일 수) |
| `[COMPACT]` | system (compact_boundary) | 컨텍스트 압축 발생 지점 |

## 타임라인 다이어그램

`timeline` 명령으로 일일 작업 타임라인을 생성합니다.

### 출력물

1. **`.drawio` 파일** (2페이지)
   - **Page 1: Timeline** — Gantt 차트 형태의 시간축 타임라인
   - **Page 2: Process Flow** — 세션별 작업 흐름도 (단계 유형별 색상/모양 구분)

2. **Companion `.md` 파일** — 상세 작업 과정 마크다운

### 단계 유형 분류

각 작업 단계는 자동으로 5가지 유형으로 분류됩니다:

| 아이콘 | 유형 | 설명 | drawio 스타일 |
|--------|------|------|---------------|
| 🔍 | ANALYSIS | 코드 분석, 파일 탐색, 구조 파악 | 파란색 둥근 사각형 |
| ⚡ | DECISION | 의사결정, 문제 발견, 접근 방법 결정 | 노란색 육각형 |
| 🔧 | IMPLEMENTATION | 코드 작성, 수정, 파일 생성 | 초록색 둥근 사각형 |
| ✅ | VERIFICATION | 테스트, 검증, 빌드 확인 | 보라색 점선 사각형 |
| 📋 | SUMMARY | 결과 정리, 요약, 완료 보고 | 갈색 둥근 사각형 |

### Companion Markdown 예시

```markdown
## Detailed Work Process

### Session `777c4ad7`

#### 15:42 - 16:24 | 로직상 이상한 부분이 있는지 확인

**Work process**:

1. ⚡ **[DECISION]** 두 컨트롤러를 비교 분석한 결과, 주요 이슈를 발견했습니다.
2. ✅ **[VERIFICATION]** 서비스 레이어까지 추적해서 확인하겠습니다.
3. 🔧 **[IMPLEMENTATION]** 모든 코드를 확인했습니다. 이제 7개 버그를 수정하겠습니다.
   - B2B rejectMeeting 히스토리 enum 수정
   - PSA reRequestMeeting 권한 체크 수정
4. 📋 **[SUMMARY]** 수정 완료 요약
```

## 설치

```bash
cd claude_log
pip install -e .
```

### 요구사항

- Python 3.8+
- jinja2 >= 3.1.0
- pyyaml >= 6.0
- watchdog >= 3.0.0
- python-dateutil >= 2.8.0

## 사용법

### 설정 초기화

```bash
claude-log-organizer init
```

### 단일 파일 처리

```bash
claude-log-organizer process .claude/logs/2026-02-19_170012_abc123.log
```

### 디렉토리 일괄 처리

```bash
claude-log-organizer batch .claude/logs/
claude-log-organizer batch .claude/logs/ --force  # 전체 재처리
```

### 디렉토리 감시 (실시간)

```bash
claude-log-organizer watch
```

### 타임라인 생성

```bash
claude-log-organizer timeline 2026-02-19
# -> summaries/daily-2026-02-19_timeline.drawio
# -> summaries/daily-2026-02-19_timeline.md
```

### 처리 이력 초기화

```bash
claude-log-organizer clear
```

## Hook 설정

### Stop Hook (로그 저장)

`.claude/hooks/save-conversation-log.sh`가 대화 종료 시 자동으로 JSONL을 `.log`로 변환합니다.

글로벌 설정 (`~/.claude/settings.json`):

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "/path/to/save-conversation-log.sh"
          }
        ]
      }
    ]
  }
}
```

### UserPromptSubmit Hook (컨텍스트 주입)

`.claude/hooks/start`가 매 프롬프트 제출 시 git 브랜치/상태 정보를 주입합니다.

## 프로젝트 구조

```
claude_log/
├── claude_log_organizer/
│   ├── cli.py                      # CLI 엔트리포인트
│   ├── config.py                   # 설정 관리
│   ├── main.py                     # 앱 오케스트레이터
│   ├── generators/
│   │   ├── markdown_generator.py   # Jinja2 마크다운 생성기
│   │   └── timeline_diagram.py     # draw.io 타임라인 + companion md
│   ├── models/
│   │   └── task_data.py            # TaskData, TimelineEntry, ProcessStep
│   ├── parsers/
│   │   ├── base_parser.py          # 파서 베이스 클래스
│   │   ├── conversation_parser.py  # conversation-task-*.log 파서
│   │   ├── session_parser.py       # 세션 .log 파서 (태그 기반)
│   │   ├── parser_factory.py       # 파서 팩토리
│   │   └── timeline_parser.py      # 타임라인 로그 파서
│   ├── storage/
│   │   └── processed_tracker.py    # 처리 이력 추적
│   └── watcher/
│       ├── file_watcher.py         # 파일 감시
│       └── event_dispatcher.py     # 이벤트 디스패처
├── templates/
│   └── default.md.jinja2           # task 마크다운 템플릿
├── .claude/
│   ├── hooks/
│   │   ├── save-conversation-log.sh  # Stop Hook (JSONL → .log)
│   │   ├── start                     # UserPromptSubmit Hook
│   │   └── stop                      # Project stop hook
│   └── settings.local.json           # 프로젝트 Hook 설정
├── tasks/                          # 생성된 task 마크다운
├── summaries/                      # 생성된 타임라인 (.drawio + .md)
├── config.yaml
├── setup.py
└── requirements.txt
```

## 설정 (config.yaml)

```yaml
watch:
  directory: ./logs
  patterns: ["conversation-task-*.log"]
  poll_interval: 1.0

output:
  directory: ./tasks
  filename_pattern: "task-{task_id}.md"
  summaries_directory: ./summaries

parsing:
  extract_code_snippets: true
  extract_phases: true
  extract_decisions: true

templates:
  directory: ./templates
  default_template: "default.md.jinja2"

storage:
  processed_log: ".processed.json"
  enable_cache: true
```

## 커스터마이징

### 템플릿 수정

`templates/default.md.jinja2`를 수정하여 task 마크다운 출력 형식을 변경할 수 있습니다.

사용 가능한 변수:
- `task.work_summary` — 작업 요약
- `task.files_modified` / `task.files_created` — 파일 변경 목록
- `task.key_decisions` — 주요 기술 결정
- `task.thinking_summary` — 사고 과정 요약
- `task.referenced_documents` — 참조 문서
- `task.metadata.compact_count` — 컨텍스트 압축 횟수

## License

MIT License
