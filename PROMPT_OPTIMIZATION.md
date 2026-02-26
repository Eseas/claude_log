# 프롬프트 최적화 가이드

AI에게 **최소한의 토큰으로 최대한 명확하게** 지시하는 방법을 학습하고 개선하는 시스템입니다.

## 🎯 목표

- **짧은 요청**: 불필요한 설명 제거, 핵심만
- **명확한 요청**: AI가 오해할 여지 없이
- **1-2회 완료**: 여러 번 왕복하지 않고
- **작은 수정 최소화**: 직접 고치는 게 빠른 상황 방지

## 📊 문제 상황

### 비효율적인 패턴

```
사용자: "파일이 이상해요"
AI: "어떤 파일인가요?"
사용자: "event_dispatcher.py요"
AI: "어떤 부분이 이상한가요?"
사용자: "debouncing이요"
AI: "어떤 상황에서 문제가 되나요?"
사용자: "created 이벤트에서요"

→ 5번 왕복
→ 많은 토큰 낭비
→ 시간 소모
```

### 효율적인 패턴

```
사용자: "event_dispatcher.py:70 created 이벤트 debounce 미적용"
AI: (바로 이해하고 수정)

→ 1번 왕복
→ 최소 토큰
→ 빠른 해결
```

## 🔍 효율성 분석 사용법

### 1. Interactive 모드 실행

```bash
python3 -m claude_log_organizer.interactive
```

### 2. Request AI 선택

```
2. Request AI - AI 요약 요청
```

### 3. 세션 선택

분석하고 싶은 세션을 선택 (단일/다중)

### 4. 효율성 분석 선택

```
분석 타입:
  → 일반 요약
  → 효율성 분석 ⭐ 선택
```

### 5. AI 방식 선택

- Claude Code CLI (추천)
- API 키

### 6. 결과 확인

`summaries/session-{id}_efficiency.md` 파일 생성됨

## 📝 분석 결과 구조

```markdown
# Session 효율성 분석: {session_id}

## 1. 세션 요약
이 세션에서 무슨 일을 했는지 2-3문장

## 2. 프롬프트 효율성 분석

### 초기 요청 분석
- **원본 요청**: "[실제 요청]"
- **포함된 정보**:
  - ✅ 파일명: event_dispatcher.py
  - ❌ 함수명: 없음
  - ❌ 현상: 모호함
  - ❌ 기대결과: 없음
- **토큰 효율성**: 하
- **명확성**: 하

### 왕복 효율성
- **총 왕복 횟수**: 5회
- **각 왕복 내용**:
  1. 초기 요청 (모호)
  2. 파일명 확인
  3. 문제 부분 확인
  4. 상황 확인
  5. 실제 수정

## 3. 최적화된 프롬프트 제안

만약 처음부터 이렇게 요청했다면:

```
event_dispatcher.py:70 _process_with_debounce
현상: created 이벤트 debounce 미적용
기대: modified처럼 3초 대기 처리
```

**개선 포인트**:
- 파일:라인 형식으로 위치 즉시 파악
- 현상을 구체적으로 기술
- 기대 동작 명확히 제시

## 4. 패턴 추출

### 요청 타입
- [x] 버그 수정

### 필수 요소
1. 파일명
2. 현상 설명
3. 기대 결과

### 생략 가능
1. 배경 설명 (필요시만)

## 5. 학습 포인트

### 효과적이었던 표현
- "파일:라인 형식"
- "현상: X, 기대: Y 구조"

### 비효율적이었던 표현
- "확인해주세요" → 무엇을?
- "이상해요" → 어떻게?

### 다음번 개선
1. 항상 파일:라인 포함
2. 현상/기대 명확히
3. 참고 코드 명시
```

## 🎨 요청 타입별 템플릿

### 버그 수정

```
파일:라인 함수명
현상: X 발생
기대: Y 되어야 함
[참고: Z 파일의 동일 패턴]
```

**예시**:
```
event_dispatcher.py:70 _process_with_debounce
현상: created 이벤트 debounce 미적용
기대: modified처럼 3초 대기
참고: file_watcher.py:45 동일 패턴
```

### 기능 추가

```
위치: 파일:함수
동작: X하면 Y 되도록
참고: 기존 Z 코드 패턴
```

**예시**:
```
위치: interactive.py:handle_ai_request_menu
동작: 효율성 분석 옵션 추가
참고: corp-report.vue:120 배너 패턴
```

### 리팩토링

```
대상: 파일:라인-라인
방식: X로 변경
제약: Y 기능 유지
```

**예시**:
```
대상: session_parser.py:100-150
방식: 응답 길이 200→1500 확대
제약: 메모리 사용량 동일 유지
```

### 코드 조사

```
목적: X 파악
범위: 파일/디렉토리
질문: Y가 어떻게 동작?
```

**예시**:
```
목적: 승인 워크플로우 파악
범위: corp-report/[meetingIdx].vue
질문: apprYn 상태별 동작 차이
```

## 📈 효율성 메트릭

### 왕복 횟수
- **1-2회**: 최고 (목표)
- **3회**: 보통 (허용)
- **4회+**: 개선 필요

### 토큰 효율성
```
효율성 = 정보량 / 문자수
```

**좋은 예**: "file.py:10 X→Y" (15자, 3개 정보) = 0.20
**나쁜 예**: "해당 파일의 그 부분을 확인해서..." (20자, 0개 정보) = 0.00

### 명확성 점수
- **상**: AI가 즉시 이해
- **중**: 1-2회 확인 필요
- **하**: 여러 번 왕복 필요

## 🔄 학습 프로세스

### 1주차: 데이터 수집
- 평일에 Claude와 작업
- 로그 자동 수집

### 주말: 분석
- 효율성 분석 실행
- 패턴 추출
- 개선점 파악

### 2주차: 적용
- 학습한 패턴 적용
- 더 짧고 명확하게 요청
- 결과 비교

### 반복
- 패턴 데이터베이스 누적
- 프롬프트 생성기 개발 (향후)

## 💾 패턴 데이터베이스

### 구조

```
prompt_optimizer/
├── patterns/
│   ├── patterns.jsonl       # 패턴 저장소
│   └── pattern_db.py        # 관리 도구
└── analyzers/
    └── session_analyzer.py  # 분석 엔진
```

### 사용 예시

```python
from prompt_optimizer.patterns.pattern_db import PatternDB

db = PatternDB()

# 효율적인 패턴 조회
efficient = db.get_efficient_patterns(pattern_type="bug_fix")
for pattern in efficient:
    print(f"원본: {pattern['original']}")
    print(f"최적: {pattern['optimized']}")
    print(f"왕복: {pattern['rounds']}회")
    print()

# 통계
stats = db.get_statistics()
print(f"총 패턴: {stats['total']}")
print(f"평균 왕복: {stats['avg_rounds']:.1f}회")
print(f"성공률: {stats['success_rate']:.1f}%")
print(f"평균 토큰 절약: {stats['avg_token_reduction']:.1f}%")
```

## 🎯 실전 팁

### DO: 이렇게 하세요

✅ **파일:라인 형식**
```
event_dispatcher.py:70
```

✅ **현상/기대 명확히**
```
현상: created 이벤트 무시됨
기대: modified처럼 처리
```

✅ **참고 코드 명시**
```
참고: file_watcher.py:45 패턴
```

✅ **에러 로그 첨부**
```
에러: "File not processed"
로그: [2026-02-13] DEBUG File unchanged
```

### DON'T: 피하세요

❌ **모호한 표현**
```
"파일이 이상해요"
"작동이 안 돼요"
"확인해주세요"
```

❌ **불필요한 배경 설명**
```
"어제부터 이 기능을 만들고 있는데,
그런데 갑자기 이상하게 동작해서..."
```

❌ **여러 요청 혼합**
```
"A도 고치고 B도 추가하고 C도 확인해주세요"
→ 각각 별도 요청
```

## 🚀 향후 계획

### Phase 1: 분석 (현재)
- [x] 효율성 분석 템플릿
- [x] 세션 분석기
- [x] 패턴 데이터베이스

### Phase 2: 학습
- [ ] 자동 패턴 추출
- [ ] 효율성 점수 계산
- [ ] 카테고리별 분류

### Phase 3: 생성 (최종 목표)
- [ ] 프롬프트 생성 도우미
- [ ] 짧은 입력 → 명확한 프롬프트
- [ ] 자동 보강 시스템

```
최종 목표:

입력: "debouncing 버그"

자동 생성:
"event_dispatcher.py:70 _process_with_debounce
현상: created 이벤트 debounce 미적용
기대: modified처럼 3초 대기
참고: 최근 수정 이력"
```

## 📚 참고 자료

- [USAGE_GUIDE.md](USAGE_GUIDE.md) - 전체 사용 가이드
- [prompt_optimizer/README.md](prompt_optimizer/README.md) - 기술 문서
- [templates/efficiency_analysis.txt](prompt_optimizer/templates/efficiency_analysis.txt) - 분석 템플릿

---

**핵심 원칙**: 짧되 명확하게, 토큰 절약하되 정보는 충분히
