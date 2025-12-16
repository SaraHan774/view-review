# 💡 편리하게 사용하기

ViewReview를 더 효율적으로 활용하는 방법들을 소개합니다.

## 1. 명령어 별칭(Alias) 설정

매번 긴 경로를 입력하지 않고 간단한 명령어로 실행할 수 있습니다.

**bash/zsh 사용자** (`~/.bashrc` 또는 `~/.zshrc`에 추가):
```bash
# 현재 디렉터리에서 코드 리뷰 체커 실행
alias reviewcheck='python /path/to/ViewReview/app.py'

# 또는 특정 저장소로 이동 후 실행
alias reviewcheck-myrepo='cd ~/projects/my-repo && python /path/to/ViewReview/app.py'
```

적용 후:
```bash
source ~/.zshrc
cd /path/to/your/repo
reviewcheck  # 간단하게 실행!
```

## 2. 실행 스크립트 생성

프로젝트마다 별도의 실행 스크립트를 만들어 관리할 수 있습니다.

**방법 1: 각 프로젝트에 스크립트 추가**
```bash
# ~/projects/my-repo/review.sh
#!/bin/bash
cd "$(dirname "$0")"
python /path/to/ViewReview/app.py
```

```bash
chmod +x ~/projects/my-repo/review.sh
~/projects/my-repo/review.sh
```

**방법 2: 글로벌 스크립트로 저장소 선택**
```bash
# ~/bin/reviewcheck (~/bin을 PATH에 추가)
#!/bin/bash

REPO_PATH="${1:-$(pwd)}"
cd "$REPO_PATH" || exit 1
python /path/to/ViewReview/app.py
```

```bash
chmod +x ~/bin/reviewcheck
reviewcheck ~/projects/my-repo  # 특정 저장소 지정
reviewcheck                      # 현재 디렉터리
```

## 3. 백그라운드 실행 및 자동 브라우저 열기

앱을 백그라운드에서 실행하고 자동으로 브라우저를 열 수 있습니다.

```bash
#!/bin/bash
# review-start.sh

cd /path/to/your/repo

# 백그라운드에서 앱 실행
python /path/to/ViewReview/app.py &
APP_PID=$!

# 앱이 시작될 때까지 대기
sleep 2

# 브라우저 자동 열기
open http://127.0.0.1:5000

echo "코드 리뷰 체커 실행 중 (PID: $APP_PID)"
echo "종료하려면: kill $APP_PID"
```

## 4. VS Code 통합

VS Code에서 작업 중인 저장소의 리뷰를 바로 확인할 수 있습니다.

**`.vscode/tasks.json` 추가:**
```json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "Start Code Review Checker",
      "type": "shell",
      "command": "python /path/to/ViewReview/app.py",
      "isBackground": true,
      "problemMatcher": [],
      "presentation": {
        "reveal": "always",
        "panel": "new"
      }
    },
    {
      "label": "Open Review Checker in Browser",
      "type": "shell",
      "command": "open http://127.0.0.1:5000",
      "dependsOn": ["Start Code Review Checker"]
    }
  ]
}
```

VS Code에서 `Cmd+Shift+P` → "Tasks: Run Task" → "Open Review Checker in Browser" 실행

## 5. 브라우저 북마크 설정

자주 사용하는 필터 조합을 북마크로 저장하세요:

- **미해결 코멘트만**: `http://127.0.0.1:5000/`
- **모든 코멘트**: `http://127.0.0.1:5000/?include_resolved=true`
- **열린 PR만**: `http://127.0.0.1:5000/?state=open`
- **병합된 PR의 모든 코멘트**: `http://127.0.0.1:5000/?state=merged&include_resolved=true`

## 6. 다중 저장소 관리

여러 저장소를 동시에 모니터링하려면 각각 다른 포트로 실행하세요:

```bash
# 터미널 1 - 프로젝트 A
cd ~/projects/project-a
FLASK_PORT=5000 python /path/to/ViewReview/app.py &

# 터미널 2 - 프로젝트 B
cd ~/projects/project-b
FLASK_PORT=5001 python /path/to/ViewReview/app.py &

# 터미널 3 - 프로젝트 C
cd ~/projects/project-c
FLASK_PORT=5002 python /path/to/ViewReview/app.py &
```

그리고 브라우저에서 각 탭으로 관리:
- Project A: http://127.0.0.1:5000
- Project B: http://127.0.0.1:5001
- Project C: http://127.0.0.1:5002

## 7. Alfred/Raycast 워크플로우 (macOS)

**Alfred Script:**
```bash
cd ~/projects/my-repo
python /path/to/ViewReview/app.py &
sleep 2
open http://127.0.0.1:5000
```

키워드 `review`를 입력하면 바로 실행됩니다.

## 8. 자동 새로고침 설정

페이지를 주기적으로 새로고침하고 싶다면 브라우저 확장 프로그램 사용:
- Chrome: "Auto Refresh Plus"
- Firefox: "Tab Reloader"

5분마다 자동 새로고침하여 최신 코멘트 상태를 확인할 수 있습니다.

## 9. 팀 공유 서버로 운영

팀원들과 함께 사용하려면:

```bash
# 외부 접속 허용
export FLASK_HOST=0.0.0.0
export FLASK_PORT=5000
python /path/to/ViewReview/app.py
```

팀원들은 `http://your-ip:5000`으로 접속할 수 있습니다.

⚠️ **보안 주의**: 외부에 노출할 경우 적절한 인증 및 방화벽 설정이 필요합니다.

## 10. 시스템 시작 시 자동 실행 (macOS)

**LaunchAgent 생성** (`~/Library/LaunchAgents/com.viewreview.plist`):
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.viewreview</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/path/to/ViewReview/app.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/path/to/your/repo</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
</dict>
</plist>
```

```bash
launchctl load ~/Library/LaunchAgents/com.viewreview.plist
```
