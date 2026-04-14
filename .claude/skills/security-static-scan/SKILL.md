---
name: security-static-scan
description: "MarsLab 보안 정적 스캔. subprocess shell=True, yaml.load vs safe_load, pickle.load, marshal.load, 경로 traversal, 하드코딩 비밀(API key/token/password), .env·credentials·*.pem 파일의 git 추적 여부, deprecated tempfile.mktemp, eval/exec 사용. CWE 기반 분류. critical 발견 시 즉시 alert. '보안 스캔', '보안 점검', 'shell injection', 'yaml load 점검', 'pickle 점검', '비밀 누출', 'security audit', '보안 회귀' 요청 시 반드시 사용."
---

# security-static-scan — MarsLab 보안 정적 스캔

`code-quality-reviewer` 에이전트가 MarsLab 소스에서 OWASP/CWE 기반 보안 결함을 정적 분석으로 감지하는 워크플로우.

## Why this matters
MarsLab은 시뮬레이션 도구지만 다음을 다룬다:
- 외부 DEM 파일·메시 파일 로딩 (경로 traversal 위험)
- YAML config 로딩 (yaml.load deserialization 위험)
- 외부 ROS2 패키지 launch (subprocess 호출)
- 향후 데이터셋 다운로드(URL fetch)

오픈소스 공개를 전제로 하므로(Apache 2.0, GitHub release v1.0.0) **비밀 노출과 임의 코드 실행 결함은 critical**이다.

## 스캔 카테고리

### S1. 명령 주입 (CWE-78)
- **패턴**:
  - `subprocess.run(..., shell=True)` + 동적 문자열
  - `os.system(<dynamic>)`
  - `subprocess.Popen(cmd, shell=True)`
- **검사**: grep `shell=True` 모든 발생, LLM이 인수가 정적 상수인지 확인
- **severity**: critical (동적 입력 + shell=True), high (정적 상수만 + shell=True)
- **권고**: `shell=False` + 인수 list 사용

### S2. 안전하지 않은 역직렬화 (CWE-502)
- **패턴**:
  - `yaml.load(f)` (Python yaml lib, vs `yaml.safe_load`)
  - `pickle.load`, `pickle.loads`, `cPickle.*`
  - `marshal.load`
  - `dill.load`, `cloudpickle.load`
- **검사**: grep + import 분석
- **severity**: critical (외부 입력 deserialization)
- **권고**: `yaml.safe_load`, JSON, msgpack, pydantic 같은 안전한 파서

### S3. 경로 traversal (CWE-22)
- **패턴**:
  - 사용자 입력·config 값을 `os.path.join(base, user_input)`로 결합 후 normalize 안 함
  - `Path(user_input).resolve()` 후 base 디렉토리 내부 검증 안 함
  - `open(user_input, 'r')` 직접
- **검사**: 파일 I/O 함수 호출의 경로 인수가 검증되었는지 LLM read
- **severity**: high
- **권고**: `Path.resolve().relative_to(base_dir)`로 escape 방지

### S4. 하드코딩 비밀 (CWE-798)
- **패턴**:
  - 문자열 변수에 `api_key`, `secret`, `token`, `password`, `private_key` 키워드
  - Base64 long string 상수
  - PEM 형식 (`-----BEGIN ... PRIVATE KEY-----`)
  - AWS/GCP credential 패턴
- **검사**: regex + LLM read
- **severity**: critical
- **권고**: 환경변수, secret manager, 또는 사용자 직접 주입

### S5. 비밀 파일 git 추적 (CWE-540)
- **패턴**: 다음 파일이 git에 추적되어 있는지
  - `.env`, `.envrc`, `*.env.local`
  - `credentials.json`, `service_account*.json`
  - `*.pem`, `*.key`, `id_rsa`
- **검사**: `git ls-files | grep -E '<pattern>'`
- **severity**: critical
- **권고**: `.gitignore`에 추가, 이미 push 되었으면 git history 정리(사용자 직접)

### S6. 임시 파일 경합 (CWE-377)
- **패턴**:
  - `tempfile.mktemp()` (deprecated, race condition)
  - `os.tempnam`, `os.tmpnam`
- **권고**: `tempfile.mkstemp()` 또는 `NamedTemporaryFile`

### S7. eval/exec 사용 (CWE-94)
- **패턴**:
  - `eval(<dynamic>)`, `exec(<dynamic>)`
  - `compile(...).eval()`
- **검사**: grep
- **severity**: critical (동적 입력), high (정적이라도 회피 권고)

### S8. SSL/TLS 검증 비활성화 (CWE-295)
- **패턴**:
  - `verify=False` (requests, httpx)
  - `ssl.CERT_NONE`
  - `urllib.request` with unverified context
- **severity**: high
- **권고**: 인증서 검증 활성, 사설 CA 시 명시적 ca_bundle

## 워크플로우

### Step 1: 스캔 범위 결정
- 입력: 변경된 파일(git diff) 또는 전수
- `marslab/`, `scripts/`, `tests/`, 그리고 `configs/` (비밀 노출 점검)
- 추가: 프로젝트 루트의 git tracked file 목록

### Step 2: 자동 grep 패스 (S1~S8)
- 각 카테고리별 정규식 grep
- 후보 라인 수집

### Step 3: LLM read 패스
- 각 후보를 컨텍스트와 함께 읽음
- false positive 제거 (예: `password` 가 변수명이지만 dummy인 경우)
- severity 확정

### Step 4: 리포트 작성
경로: `_workspace/reviews/{wk}_security_scan.md`

포맷:
```
## Security Scan Report — Wk{N}

### Critical Issues (must fix immediately)
1. **CWE-502 — yaml.load** at marslab/config/loader.py:34
   - Code: `data = yaml.load(f)`
   - Why: untrusted YAML can execute Python objects.
   - Fix: `data = yaml.safe_load(f)`

### High Issues
2. **CWE-22 — path traversal** at marslab/terrain/dem_loader.py:78
   ...

### Medium / Low / Info
...

### Summary
- critical: 1
- high: 2
- medium: 0
- low: 0
- info: 1

### Files Scanned
- 34 .py files
- 12 .yaml files
- 1 .gitignore
```

### Step 5: critical alert
- critical 이슈가 있으면 SendMessage로 즉시 오케스트레이터 + 해당 에이전트 + qa-validator 에 통지
- 해당 작업을 blocked 로 표시 요청

### Step 6: 회귀 비교
- 이전 보안 스캔 리포트와 비교
- 같은 결함 재발 시 "regression" 마킹 + severity 한 단계 상승

### Step 7: 비밀 git 추적 추가 점검
- `git ls-files | grep -E '\.(env|pem|key)$'` 같은 패턴으로 별도 점검
- 추적된 비밀이 있으면 critical, 사용자에 git history 정리 안내(자동 수정 금지)

## 안전 원칙
- 자동 수정 금지. 권고만.
- false positive는 정직하게 제거.
- 비밀 의심 문자열을 리포트에 그대로 인용하지 말고 마스킹(`api_key="sk_***"` 형식).
- git history 수정·force push 같은 destructive 명령은 절대 자동 실행하지 않는다.

## 후속 작업 키워드
"보안 스캔 다시", "yaml load 점검", "pickle 점검", "shell injection 점검", "비밀 누출 점검", "보안 회귀" 후속 요청 시 사용. 이전 스캔 리포트와 비교.

## 테스트 프롬프트
1. "현재 marslab/ 보안 스캔 — yaml.load·subprocess·비밀 위주로."
2. ".env가 git에 추적 중인지 점검."
3. "pickle.load 사용처 전수 검색."
