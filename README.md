# 코드 리뷰 체커 (ViewReview)

GitHub PR의 리뷰 코멘트를 한눈에 확인하는 웹 애플리케이션입니다.

## Demo 

![Image](https://github.com/user-attachments/assets/5cd58796-79e7-4ee1-88e2-1071a2b4d6e6)

![Image](https://github.com/user-attachments/assets/62c9d1b6-59ad-4ee7-abd4-2b1912d00cf8)

## 주요 기능

내가 생성한 PR과 리뷰 코멘트를 조회하고 필터링할 수 있습니다.
- PR 상태별 필터 (열림/닫힘/병합됨)
- 미해결/해결된 코멘트 구분
- Diff 위치와 함께 코멘트 표시

## 전제 조건

**gh CLI 설치 및 인증** (필수)
```bash
brew install gh
gh auth login
```

## 사용 방법

**1. 패키지 설치**
```bash
cd /path/to/ViewReview
pip install -r requirements.txt
```

**2. 조회할 Git 저장소로 이동**
```bash
cd /path/to/your/repo
```

**3. 앱 실행**
```bash
python /path/to/ViewReview/app.py
```

**4. 브라우저 접속**
```
http://127.0.0.1:5000
```

앱이 현재 디렉터리의 Git 저장소를 자동 감지하여 내 PR과 리뷰 코멘트를 보여줍니다.

> 💡 더 편리하게 사용하는 방법은 [TIPS.md](TIPS.md)를 참고하세요.

## 기술 스택

- **Python 3.7+**, **Flask** - 웹 프레임워크
- **GitHub CLI (gh)** - GitHub API 인터페이스
- **Jinja2**, **HTML/CSS/JS** - 프론트엔드

## 설정 커스터마이징

### 데이터 로드 제한 설정

한 페이지에 로드할 수 있는 최대 개수를 환경 변수로 설정할 수 있습니다:

```bash
# PR 목록 최대 개수 (기본값: 100)
export MAX_PR_LIST_LIMIT=200

# PR당 최대 리뷰 스레드 개수 (기본값: 100)
export MAX_REVIEW_THREADS=150

# 스레드당 최대 코멘트 개수 (기본값: 100)
export MAX_COMMENTS_PER_THREAD=200

# PR당 최대 커밋 개수 (기본값: 100)
export MAX_COMMITS=150

python app.py
```

또는 `config.py` 파일에서 직접 수정할 수 있습니다.

### 현재 기본 제한값

- **PR 목록**: 최대 100개 (gh CLI 기본값 30개를 초과하는 경우 `--limit` 옵션 사용)
- **리뷰 스레드**: PR당 최대 100개
- **코멘트**: 스레드당 최대 100개
- **커밋**: PR당 최대 100개

> ⚠️ **주의**: GitHub GraphQL API는 한 번에 최대 100개까지만 조회 가능합니다. 더 많은 데이터가 필요한 경우 페이지네이션을 구현해야 합니다.

## 트러블슈팅

**gh CLI 인증 오류**
```bash
gh auth login
```

**포트 이미 사용 중**
```bash
export FLASK_PORT=8080
python app.py
```

**Git 저장소가 아닌 디렉터리에서 실행**
→ Git 저장소의 루트 디렉터리로 이동 후 실행

## 라이선스

MIT License
