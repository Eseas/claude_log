# 빠른 시작: 인터랙티브 모드

## 1분 안에 시작하기

### 1단계: 의존성 설치

```bash
cd /Users/eseas/Desktop/mine/claude_log
python3 -m pip install inquirer anthropic
```

### 2단계: 인터랙티브 모드 실행

```bash
python3 -m claude_log_organizer.interactive
```

### 3단계: 메뉴 선택

```
============================================================
Claude Log Organizer - Interactive Mode
============================================================

작업을 선택하세요:
❯ 1. Watch - 디렉토리 모니터링 시작
  2. Request AI - AI 요약 요청
  3. Exit - 종료
```

화살표 키로 이동, Enter로 선택!

---

## 주요 기능

### 🔍 Watch - 로그 모니터링

```
선택 1 → Watch
  ↓
Config 또는 Manual 선택
  ↓
자동 감시 시작!
```

**Config 방식:**
- `config.yaml`의 디렉토리 사용
- 여러 프로젝트 동시 감시 가능

**Manual 방식:**
- 직접 경로 입력
- 일회성 감시에 적합

### 🤖 Request AI - AI 요약

```
선택 2 → Request AI
  ↓
파일 선택 (Space로 체크)
  ↓
AI 요약 자동 생성!
```

**선택 옵션:**
- `[ All ]` - 모든 파일 한번에
- 개별 선택 - Space로 체크박스 토글
- `[ Cancel ]` - 취소

---

## 조작법 요약

### 메뉴 네비게이션
- **↑/↓** : 항목 이동
- **Enter** : 선택 확인
- **Ctrl+C** : 취소/종료

### 파일 선택 (Checkbox)
- **↑/↓** : 항목 이동
- **Space** : 선택/해제 토글
- **Enter** : 선택 완료
- **Ctrl+C** : 취소

### Watch 모드
- **Ctrl+C** : 모니터링 중지

---

## 첫 실행 체크리스트

### ✅ 필수 준비사항
- [ ] Python 3.8 이상 설치
- [ ] `inquirer` 패키지 설치
- [ ] `config.yaml` 파일 생성

### ⚡ AI 기능 사용 시
- [ ] `anthropic` 패키지 설치
- [ ] Claude API 키 발급
- [ ] API 키 입력/저장

---

## 예시: 첫 실행

```bash
# 1. 패키지 설치
python3 -m pip install inquirer anthropic

# 2. 실행
python3 -m claude_log_organizer.interactive

# 3. Watch 선택
[?] 작업을 선택하세요:
 ❯ 1. Watch - 디렉토리 모니터링 시작

# 4. Manual 선택
[?] 디렉토리 선택 방법:
 ❯ 2. Manual - 직접 입력

# 5. 디렉토리 입력
📝 모니터링할 디렉토리를 입력하세요
디렉토리 1: ./logs
✓ 추가됨: /Users/eseas/Desktop/mine/claude_log/logs
디렉토리 2: [Enter]

# 6. 모니터링 시작!
⏳ 모니터링을 시작합니다...
```

---

## 문제 해결

### inquirer 임포트 에러
```bash
python3 -m pip install inquirer --upgrade
```

### API 키 관련
- 키 발급: https://console.anthropic.com/account/keys
- 설정 저장: `config.yaml`의 `ai.api_key`

### 터미널 호환성
- macOS Terminal ✅
- iTerm2 ✅
- VS Code 터미널 ✅
- Windows CMD ⚠️ (inquirer 제한적 지원)

---

## 자세한 가이드

- [INTERACTIVE_MODE.md](INTERACTIVE_MODE.md) - 전체 기능 설명
- [USAGE_GUIDE.md](USAGE_GUIDE.md) - 일반 CLI 사용법
- [README.md](README.md) - 프로젝트 개요
