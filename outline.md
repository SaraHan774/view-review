다음 예시는 gh CLI + GitHub GraphQL API를 이용해서
	•	현재 repo 기준,
	•	내가 올린 모든 PR 목록을 가져오고,
	•	각 PR의 unresolved 리뷰 코멘트를 조회한 뒤
	•	로컬 웹앱(Flask)에서
	•	PR 제목 / 번호
	•	diff hunk
	•	코멘트 작성자
	•	포매팅된 코멘트 본문(body, GitHub 포맷 그대로)
	•	코멘트로 이동하는 링크

를 한 페이지에서 보여주는 코드입니다.

전제 조건은 다음과 같습니다.
	•	gh CLI 설치 및 gh auth login 으로 GitHub 인증이 되어 있어야 합니다.
	•	pip install flask 로 Flask 를 설치합니다.
	•	이 스크립트는 PR 을 조회할 Git 저장소 루트 디렉터리에서 실행합니다.

⸻

1. 파이썬 웹앱 전체 코드 (단일 파일)

app.py 같은 이름으로 저장합니다.

#!/usr/bin/env python3
import json
import subprocess
from typing import List, Dict, Any

from flask import Flask, render_template_string
from markupsafe import Markup


app = Flask(__name__)


def run_gh(args: List[str]) -> str:
    """gh CLI를 호출하고 stdout을 문자열로 반환한다."""
    result = subprocess.run(
        ["gh"] + args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def get_repo_info() -> Dict[str, str]:
    """현재 repo의 owner, name 을 gh CLI로 조회한다."""
    owner = run_gh(["repo", "view", "--json", "owner", "-q", ".owner.login"])
    name = run_gh(["repo", "view", "--json", "name", "-q", ".name"])
    return {"owner": owner, "name": name}


def get_my_pr_numbers(state: str = "all") -> List[int]:
    """
    내가 생성한 PR 번호 목록을 gh CLI로 조회한다.

    state: "open", "closed", "merged", "all"
    """
    output = run_gh([
        "pr", "list",
        "--author", "@me",
        "--state", state,
        "--json", "number",
        "-q", ".[].number",
    ])
    if not output:
        return []
    return [int(line) for line in output.splitlines() if line.strip()]


def get_unresolved_comments_for_pr(owner: str, name: str, number: int) -> Dict[str, Any]:
    """
    단일 PR(number)에 대해 PR 메타 정보 + unresolved review comment 목록을 반환한다.

    반환 형태:
    {
      "number": 123,
      "title": "...",
      "url": "https://github.com/owner/repo/pull/123",
      "comments": [
        {
          "url": "...discussion...",
          "path": "src/...",
          "diffHunk": "@@ ...",
          "author": "login",
          "authorUrl": "https://github.com/login",
          "bodyHTML": "<p>...</p>..."
        },
        ...
      ]
    }
    """

    query = r"""
      query($owner: String!, $name: String!, $number: Int!) {
        repository(owner: $owner, name: $name) {
          pullRequest(number: $number) {
            number
            title
            url
            reviewThreads(first: 100) {
              nodes {
                isResolved
                comments(first: 100) {
                  nodes {
                    url
                    path
                    diffHunk
                    bodyHTML
                    author {
                      login
                      url
                    }
                  }
                }
              }
            }
          }
        }
      }
    """

    raw = run_gh([
        "api", "graphql",
        "-f", f"owner={owner}",
        "-f", f"name={name}",
        "-F", f"number={number}",
        "-f", f"query={query}",
    ])

    data = json.loads(raw)

    pr = (
        data.get("data", {})
        .get("repository", {})
        .get("pullRequest", {})
    )

    if not pr:
        return {}

    threads = (
        pr.get("reviewThreads", {})
        .get("nodes", [])
    )

    comments: List[Dict[str, Any]] = []

    for thread in threads:
        if thread.get("isResolved"):
            # resolved thread는 스킵
            continue

        nodes = thread.get("comments", {}).get("nodes", []) or []
        for c in nodes:
            author = c.get("author") or {}
            comments.append(
                {
                    "url": c.get("url"),
                    "path": c.get("path"),
                    "diffHunk": c.get("diffHunk"),
                    "author": author.get("login"),
                    "authorUrl": author.get("url"),
                    "bodyHTML": c.get("bodyHTML"),
                }
            )

    return {
        "number": pr.get("number"),
        "title": pr.get("title"),
        "url": pr.get("url"),
        "comments": comments,
    }


@app.route("/")
def index():
    repo = get_repo_info()
    owner = repo["owner"]
    name = repo["name"]

    pr_numbers = get_my_pr_numbers(state="all")

    prs_with_comments: List[Dict[str, Any]] = []

    for pr_number in pr_numbers:
        pr_data = get_unresolved_comments_for_pr(owner, name, pr_number)
        if not pr_data:
            continue
        if not pr_data.get("comments"):
            continue

        # bodyHTML은 그대로 렌더링할 수 있도록 Markup 래핑
        for c in pr_data["comments"]:
            c["bodyHTML_safe"] = Markup(c["bodyHTML"] or "")

        prs_with_comments.append(pr_data)

    # 간단한 HTML 템플릿 (Jinja2)
    template = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Unresolved Review Comments</title>
  <style>
    body {
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      margin: 2rem;
    }
    .pr {
      border: 1px solid #ddd;
      border-radius: 8px;
      padding: 1rem 1.5rem;
      margin-bottom: 2rem;
      background: #fafafa;
    }
    .pr-title {
      font-size: 1.1rem;
      font-weight: bold;
      margin-bottom: 0.3rem;
    }
    .pr-meta {
      font-size: 0.9rem;
      color: #555;
      margin-bottom: 1rem;
    }
    .comment {
      border-top: 1px solid #e0e0e0;
      padding-top: 0.75rem;
      margin-top: 0.75rem;
    }
    .comment-header {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      margin-bottom: 0.25rem;
      font-size: 0.9rem;
    }
    .comment-author a {
      text-decoration: none;
      color: #0366d6;
    }
    .comment-link a {
      font-size: 0.8rem;
      text-decoration: none;
      color: #0366d6;
    }
    .comment-path {
      font-size: 0.85rem;
      color: #666;
      margin-bottom: 0.2rem;
    }
    pre.diff {
      background: #222;
      color: #eee;
      padding: 0.5rem 0.75rem;
      border-radius: 4px;
      overflow-x: auto;
      font-size: 0.8rem;
      line-height: 1.2;
      margin-bottom: 0.4rem;
    }
    pre.diff code {
      white-space: pre;
    }
    .comment-body {
      border: 1px solid #e0e0e0;
      border-radius: 4px;
      padding: 0.5rem 0.75rem;
      background: #fff;
      font-size: 0.9rem;
    }
  </style>
</head>
<body>
  <h1>Unresolved Review Comments (authored PRs)</h1>

  {% if prs %}
    {% for pr in prs %}
      <div class="pr">
        <div class="pr-title">
          <a href="{{ pr.url }}" target="_blank" rel="noopener noreferrer">
            #{{ pr.number }} - {{ pr.title }}
          </a>
        </div>
        <div class="pr-meta">
          {{ owner }}/{{ name }}
        </div>

        {% for c in pr.comments %}
          <div class="comment">
            <div class="comment-header">
              <div class="comment-author">
                {% if c.authorUrl %}
                  <a href="{{ c.authorUrl }}" target="_blank" rel="noopener noreferrer">
                    {{ c.author }}
                  </a>
                {% else %}
                  {{ c.author }}
                {% endif %}
              </div>
              <div class="comment-link">
                {% if c.url %}
                  <a href="{{ c.url }}" target="_blank" rel="noopener noreferrer">
                    open on GitHub
                  </a>
                {% endif %}
              </div>
            </div>

            {% if c.path %}
              <div class="comment-path">{{ c.path }}</div>
            {% endif %}

            {% if c.diffHunk %}
              <pre class="diff"><code>{{ c.diffHunk }}</code></pre>
            {% endif %}

            <div class="comment-body">
              {{ c.bodyHTML_safe }}
            </div>
          </div>
        {% endfor %}
      </div>
    {% endfor %}
  {% else %}
    <p>unresolved 리뷰 코멘트가 있는 PR 이 없습니다.</p>
  {% endif %}
</body>
</html>
    """

    return render_template_string(template, prs=prs_with_comments, owner=owner, name=name)


if __name__ == "__main__":
    # 기본적으로 http://127.0.0.1:5000 에서 실행
    app.run(debug=True)


⸻

2. 동작 방식 요약
	1.	get_repo_info()
gh repo view --json owner,name 를 사용하여 현재 origin 기준 owner / repo 정보를 가져옵니다.
	2.	get_my_pr_numbers(state="all")
gh pr list --author @me --state all 을 통해 이 저장소에서 내가 만든 모든 PR 번호를 얻습니다.
	3.	get_unresolved_comments_for_pr()
각 PR 번호에 대해 GitHub GraphQL API의 pullRequest.reviewThreads 를 조회하고,
isResolved == false 인 스레드만 필터링한 뒤, 각 스레드의 comments.nodes 에서
	•	url (코멘트 링크)
	•	path (파일 경로)
	•	diffHunk (코멘트가 달린 코드에 대한 unified diff hunk)
	•	bodyHTML (GitHub 가 렌더링하는 HTML 버전의 코멘트 본문)
	•	author.login, author.url (작성자 정보)
를 수집합니다.
	4.	Flask 라우트(/)
	•	위 데이터를 모아서 unresolved 코멘트가 하나 이상 있는 PR만 남깁니다.
	•	bodyHTML은 GitHub 가 이미 sanitzed HTML 을 반환하므로 Markup 으로 감싸 그대로 렌더합니다.
	•	템플릿에서 각 PR을 카드 형태로 보여주고,
	•	diff hunk는 <pre class="diff"><code>...</code></pre> 로 표시,
	•	작성자는 GitHub 프로필 링크,
	•	“open on GitHub” 링크를 누르면 해당 코멘트 페이지로 이동하도록 구성했습니다.
	5.	실행 방법

pip install flask markupsafe
python app.py

브라우저에서 http://127.0.0.1:5000 에 접속하면,
내가 올린 PR들 중 unresolved 리뷰 코멘트가 있는 PR 목록과 각 코멘트의 diff / 작성자 / 포매팅된 본문 / GitHub 링크를 확인할 수 있습니다.

⸻

사용한 웹사이트 목록:

https://docs.github.com/en/graphql
https://docs.github.com/ko/graphql
https://docs.github.com/en/graphql/guides/forming-calls-with-graphql
https://docs.github.com/ko/graphql/guides/introduction-to-graphql
https://www.imtala.com/docs/github/PullRequestReviewComment
https://www.exchangetuts.com/pull-request-review-comment-wrong-position-from-the-diff-1757854202439703
https://cli.github.com/manual/gh
https://github.blog/developer-skills/github/exploring-github-cli-how-to-interact-with-githubs-graphql-api-endpoint