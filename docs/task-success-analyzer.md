# Task Success/Failure Analyzer - 개발 분석 문서

> 작성일: 2026-03-17
> 상태: Phase 1 완료 / Phase 2~5 개발 예정

---

## 1. 개요

### 목적
Claude Code 세션 내에서 사용자가 요청한 작업이 성공했는지 실패했는지를 **다음 메시지의 반응**으로 판단하는 분석기.

### 판단 방식 (병렬 실행, 결과 분리 표시)
1. **시그널 기반 (Heuristic)** — 키워드/패턴 매칭으로 즉시 판정
2. **AI 기반** — Claude CLI를 통해 문맥을 이해하여 판정

### 핵심 개념: TaskInteraction
```
[USER] 요청 A
  [ASSISTANT] 응답 + [TOOL] 실행 + [TOOL_RESULT]
[USER] 요청 B  ← 이 메시지가 요청 A의 "피드백"
  [ASSISTANT] 응답 ...
[USER] 요청 C  ← 이 메시지가 요청 B의 "피드백"
```

---

## 2. 현재 구현 (Phase 1) — v1.2

### 2.1 개발 기간
- 2026-03-12 ~ 2026-03-17 (v1.2 커밋에 포함)

### 2.2 추가된 파일/모듈

| 파일 | 역할 |
|------|------|
| `analyzers/task_success_analyzer.py` | 핵심 분석 엔진 (482줄) |
| `models/task_data.py` (TaskInteraction 추가) | 상호작용 데이터 모델 (34줄 추가) |
| `interactive.py` (task_success 메뉴 추가) | CLI 메뉴 통합 (126줄 추가) |

### 2.3 구현된 로직

#### A. 상호작용 추출 (`extract_interactions`)

```
로그 내용을 [USER] 태그 기준으로 분할
  → 각 세그먼트에서 추출:
    - user_msg: [USER] 텍스트
    - assistant_responses: [ASSISTANT] 텍스트들
    - tools: [TOOL] 호출 정보
    - tool_results: [TOOL_RESULT] 결과들
  → 비-사용자 메시지 필터링:
    - [TOOL_RESULT], <ide_*>, [Request interrupted, <system, 세션 연속 안내
  → feedback 연결: 다음 유효한 [USER] 메시지를 현재 상호작용의 피드백으로 연결
  → TaskInteraction 객체 생성
```

#### B. 시그널 분석 (`analyze_heuristic`)

**실패 시그널** (13개 패턴):

| 카테고리 | 패턴 예시 | 가중치 |
|----------|-----------|--------|
| 부정 표현 | 아니, 아닌데, 아니야 | 0.7 |
| 수정 요청 | 그게 아니라, 그거 말고 | 0.8 |
| 오류 지적 | 틀렸, 잘못 | 0.9 |
| 재시도 요청 | 다시 해, 다시 만들 | 0.85 |
| 수정/고침 | 수정해, 고쳐, fix | 0.75 |
| 에러 언급 | 에러, 오류, 실패, 안 돼 | 0.8 |
| 동작 불가 | 작동 안, 안 나와 | 0.8 |
| 미해결 | 아직, 여전히, 계속 | 0.6 |
| 영문 패턴 | wrong, incorrect, broken | 0.6~0.8 |

**성공 시그널** (8개 패턴):

| 카테고리 | 패턴 예시 | 가중치 |
|----------|-----------|--------|
| 긍정 확인 | 좋아, 잘 됐, 좋습니다 | 0.8 |
| 감사 | 감사, 고마워, thanks | 0.7 |
| 정확성 확인 | 완벽, 정확, 맞아 | 0.9 |
| 승인 | 오케이, ㅇㅋ, good, perfect | 0.7 |
| 후속 전환 | 이제, 그러면, 다음 | 0.6 |
| 추가 요청 | 추가로, 또, 하나 더 | 0.5 |
| 영문 패턴 | works, done, solved | 0.8 |

**도구 에러 시그널** (3개 패턴):
- Error/Exception/Traceback → 0.7 (×0.5 감쇠)
- FAILED/failure → 0.7 (×0.5 감쇠)
- command not found / Permission denied → 0.6 (×0.5 감쇠)

**보조 판단 로직**:
- `_is_topic_change()`: 요청과 피드백의 키워드 중첩률 < 15% → 주제 전환 (성공 +0.4)
- `_text_similarity()`: Jaccard 유사도 > 50% → 같은 요청 반복 (실패 +0.6)

**판정 규칙**:
```
failure_score vs success_score 비교
  failure > success → "failure" (확신도 = failure / total)
  success > failure → "success" (확신도 = success / total)
  동점 → "partial" (확신도 = 0.5)
  양쪽 모두 0 → "unknown" (확신도 = 0.0)
  feedback 없음 (마지막 메시지) → "unknown"
```

#### C. AI 분석 (`analyze_ai`)

```
1. Claude CLI 존재 확인 (shutil.which("claude"))
2. feedback이 있는 상호작용만 필터링
3. 배치 프롬프트 구성:
   - 각 상호작용의 request, assistant_work, tools, feedback 포함
   - JSON 형식 응답 요구: [{result, confidence, reasoning}]
4. subprocess.run("claude -p <prompt> --output-format json")
5. 응답에서 JSON 배열 추출 (regex)
6. 각 상호작용에 ai_result, ai_confidence, ai_reasoning 저장
```

**에러 처리**:
- CLI 없음 → "unknown" + 메시지
- CLI 실행 실패 → stderr 앞 200자 기록
- 타임아웃 (120초) → "unknown" + 메시지
- JSON 파싱 실패 → "unknown" + 에러 내용

#### D. 리포트 생성 (`generate_report`)

```
1. Overview 섹션
   - 총 상호작용 수, 피드백 있는 수
   - 시그널/AI별 success/failure/partial/unknown 카운트 + 성공률 테이블

2. Signal-based Analysis 섹션
   - 각 상호작용의 판정 결과, 요청/피드백 미리보기, 감지된 시그널 목록

3. AI-based Analysis 섹션
   - 각 상호작용의 AI 판정, 확신도, 판단 근거

4. Disagreements 섹션
   - 시그널과 AI 판정이 불일치하는 항목 테이블
   - 양쪽 근거 비교
```

---

## 3. 추가 개발 계획

### Phase 2: 실패 패턴 분류 (Failure Categorization)

**목적**: 단순 성공/실패를 넘어 실패 원인을 카테고리별로 분류

**추가할 카테고리**:

| 카테고리 | 설명 | 판단 기준 |
|----------|------|-----------|
| `misunderstanding` | 요구사항 이해 실패 | "그게 아니라", "내가 원하는 건", 요청과 응답의 주제 불일치 |
| `execution_error` | 코드/도구 실행 에러 | tool_results에 Error/Exception, Bash 도구 실패 |
| `incomplete` | 불완전한 구현 | "나머지", "빠졌", "더 있", "추가해", 후속 동일 주제 요청 |
| `wrong_approach` | 접근 방식 자체 잘못 | "그 방법 말고", "다른 방식으로", "처음부터" |

**구현 위치**: `TaskInteraction` 모델에 `failure_category: Optional[str]` 필드 추가

**로직 추가**:
```python
# task_success_analyzer.py에 추가
def _categorize_failure(self, interaction: TaskInteraction) -> str:
    """실패한 상호작용의 원인 카테고리 분류."""
    # 1. 도구 에러 체크 (execution_error)
    # 2. 이해 실패 패턴 체크 (misunderstanding)
    # 3. 불완전 패턴 체크 (incomplete)
    # 4. 잘못된 접근 패턴 체크 (wrong_approach)
    # 5. 폴백 → "unclassified"
```

**리포트 추가**: 실패 카테고리별 통계 파이 차트 (텍스트 기반)

**예상 작업량**: TaskInteraction 모델 수정 + 분석기에 60~80줄 + 리포트에 20줄

---

### Phase 3: 연속 실패 감지 (Failure Streak Detection)

**목적**: 같은 주제에서 연속 실패 시 근본적 문제 가능성 경고

**로직**:
```python
def detect_failure_streaks(self, interactions: List[TaskInteraction]) -> List[FailureStreak]:
    """연속 실패 패턴 감지.

    판단 기준:
    1. 연속 2회 이상 failure/partial 판정
    2. 주제 유사도 > 40% (같은 작업 반복 시도)
    3. 최종 해결 여부 추적 (마지막이 success면 "resolved")
    """
```

**추가할 데이터 모델**:
```python
@dataclass
class FailureStreak:
    start_index: int                    # 시작 상호작용 인덱스
    end_index: int                      # 종료 인덱스
    length: int                         # 연속 실패 횟수
    topic: str                          # 공통 주제 (키워드 추출)
    resolved: bool                      # 최종 해결 여부
    interactions: List[TaskInteraction] # 관련 상호작용들
```

**리포트 추가**:
```markdown
### Failure Streaks (연속 실패 패턴)

#### Streak 1: "debouncing 관련" (3회 연속 실패 → 해결)
- [2] ❌ → [3] ❌ → [4] ⚠️ → [5] ✅ 해결
- 근본 원인 추정: 설정 파일 경로 불일치
```

**예상 작업량**: FailureStreak 모델 + 감지 로직 50줄 + 리포트 30줄

---

### Phase 4: 복잡도 vs 성공률 상관관계

**목적**: 작업 복잡도가 높을수록 실패율이 높아지는지 분석

**복잡도 지표**:

| 지표 | 산출 방법 | 가중치 |
|------|-----------|--------|
| 도구 사용 횟수 | `len(tools_used)` | 0.3 |
| Assistant 응답 길이 | `sum(len(r) for r in assistant_work)` | 0.2 |
| 도구 결과 에러 비율 | error_results / total_results | 0.3 |
| 요청 길이 | `len(request)` | 0.1 |
| 도구 종류 다양성 | `len(set(t['tool'] for t in tools_used))` | 0.1 |

**로직**:
```python
def analyze_complexity_correlation(self, interactions: List[TaskInteraction]) -> Dict:
    """복잡도와 성공률 상관관계 분석.

    반환:
    - complexity_buckets: {low: {total, success_rate}, medium: ..., high: ...}
    - correlation_coefficient: float (-1 ~ 1)
    - high_complexity_failures: List[TaskInteraction]
    """
```

**리포트 추가**:
```markdown
### Complexity vs Success Rate

| 복잡도 | 상호작용 수 | 성공률 | 평균 도구 수 |
|--------|------------|--------|-------------|
| Low (0-3 tools) | 8 | 87% | 1.5 |
| Medium (4-8 tools) | 5 | 60% | 5.8 |
| High (9+ tools) | 3 | 33% | 12.3 |

> 상관계수: -0.72 (복잡도 ↑ → 성공률 ↓ 강한 음의 상관)
```

**예상 작업량**: 복잡도 계산 40줄 + 상관분석 30줄 + 리포트 25줄

---

### Phase 5: 도구별 에러율 분석

**목적**: 어떤 도구에서 에러가 가장 많이 발생하는지 통계

**로직**:
```python
def analyze_tool_error_rates(self, interactions: List[TaskInteraction]) -> Dict[str, ToolStats]:
    """도구별 에러율 분석.

    각 상호작용에서:
    1. tools_used에서 도구 이름 추출
    2. tool_results에서 에러 패턴 매칭
    3. 도구 호출 직후의 결과를 매칭하여 도구별 에러율 계산
    """
```

**추가할 데이터 모델**:
```python
@dataclass
class ToolStats:
    tool_name: str
    total_calls: int
    error_count: int
    error_rate: float           # error_count / total_calls
    common_errors: List[str]    # 자주 발생하는 에러 메시지 (상위 3개)
```

**리포트 추가**:
```markdown
### Tool Error Rates

| 도구 | 호출 수 | 에러 수 | 에러율 | 주요 에러 |
|------|---------|---------|--------|-----------|
| Bash | 45 | 8 | 17.8% | command not found, exit code 1 |
| Edit | 23 | 3 | 13.0% | old_string not unique |
| Write | 12 | 0 | 0.0% | - |
```

**예상 작업량**: ToolStats 모델 + 분석 로직 50줄 + 리포트 20줄

---

## 4. 개발 로드맵

```
Phase 1 (완료)     Phase 2          Phase 3          Phase 4          Phase 5
v1.2               v1.3             v1.3             v1.4             v1.4
─────────────────┬────────────────┬────────────────┬────────────────┬────────────────
기본 시그널/AI    │ 실패 카테고리   │ 연속 실패 감지  │ 복잡도-성공률   │ 도구별 에러율
분석 + 리포트     │ 분류            │ + 해결 추적     │ 상관분석       │ 분석
                  │                 │                 │                │
수정 파일:        │ 수정 파일:      │ 수정 파일:      │ 수정 파일:     │ 수정 파일:
- task_data.py    │ - task_data.py  │ - task_data.py  │ - analyzer.py  │ - task_data.py
- analyzer.py     │ - analyzer.py   │ - analyzer.py   │ (report만 추가)│ - analyzer.py
- interactive.py  │ (report 확장)   │ (report 확장)   │                │ (report 확장)
                  │                 │                 │                │
~480줄 추가       │ ~100줄 추가     │ ~80줄 추가      │ ~95줄 추가     │ ~70줄 추가
```

---

## 5. 아키텍처 고려사항

### 기존 모듈과의 관계
```
task_success_analyzer.py
  ├── 입력: .log 파일 (SessionParser와 같은 소스)
  │   └── 단, SessionParser는 TaskData를 생성하고
  │       TaskSuccessAnalyzer는 TaskInteraction을 생성 (다른 관점)
  ├── AI: Claude CLI 의존 (timeline_diagram.py의 _ai_summarize_phases와 동일 패턴)
  └── 출력: generate_report() → markdown lines (timeline_diagram.py의 _analyze_token_usage와 동일 패턴)
```

### 설계 원칙
- **시그널과 AI는 독립 실행**: AI 없이도 시그널 분석만으로 유의미한 결과 제공
- **배치 프롬프트**: 상호작용을 개별이 아닌 한 번의 API 호출로 일괄 분석 (비용/시간 효율)
- **필터링 우선**: TOOL_RESULT, IDE 이벤트 등 비-사용자 메시지를 정확히 필터링해야 오판 방지
- **피드백 없는 마지막 메시지**: 판정 불가(unknown)로 처리 — 추측하지 않음
