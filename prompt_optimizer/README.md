# Prompt Optimizer

AI 프롬프트 효율성 분석 및 최적화 도구

## 목표

**최소한의 토큰으로 최대한 명확한 지시**를 할 수 있도록 도와주는 시스템

- 과거 세션 분석 → 효율적/비효율적 패턴 학습
- 짧은 입력 → 명확한 프롬프트 자동 생성
- 작은 수정이 적어지도록 = 1-2회 왕복으로 완료

## 구조

```
prompt_optimizer/
├── analyzers/
│   └── session_analyzer.py     # 세션 효율성 분석
├── patterns/
│   ├── pattern_db.py           # 패턴 데이터베이스
│   └── patterns.jsonl          # 패턴 저장소
├── templates/
│   └── efficiency_analysis.txt # AI 분석용 템플릿
└── README.md
```

## 사용 방법

### 1. 세션 효율성 분석

claude_log_organizer의 "Request AI" 메뉴에서 효율성 분석 모드 사용

```bash
2. Request AI - AI 요약 요청
   → 효율성 분석 모드 선택
```

### 2. 패턴 데이터베이스

효율적인 프롬프트 패턴을 자동으로 학습하고 저장

```python
from prompt_optimizer.patterns.pattern_db import PatternDB

db = PatternDB()

# 효율적인 패턴 조회
efficient = db.get_efficient_patterns(pattern_type="bug_fix")

# 통계 확인
stats = db.get_statistics()
print(f"평균 왕복 횟수: {stats['avg_rounds']}")
print(f"평균 토큰 절약: {stats['avg_token_reduction']}%")
```

## 다음 단계

- [ ] interactive.py에 효율성 분석 모드 통합
- [ ] 프롬프트 생성기 구현
- [ ] CLI 도구 추가
- [ ] 패턴 시각화

## 효율성 메트릭

- **왕복 횟수**: 1-2회 = 최고, 3회 = 보통, 4회 이상 = 개선 필요
- **토큰 효율성**: (정보량 / 문자수) 비율
- **명확성**: AI가 오해할 가능성
- **완성도**: 첫 시도 성공률
