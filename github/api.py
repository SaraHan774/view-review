"""GitHub CLI 및 GraphQL API 래퍼"""

import json
import subprocess
from typing import List, Dict, Any, Optional
from operator import itemgetter


class GitHubAPIError(Exception):
    """GitHub API 관련 에러"""
    pass


class GitHubAPI:
    """GitHub CLI를 사용한 API 클라이언트"""

    @staticmethod
    def _extract_line_info(diff_hunk: str) -> str:
        """diff hunk에서 라인 정보 추출"""
        if not diff_hunk:
            return ""
        
        lines = diff_hunk.split('\n')
        for line in lines:
            if line.startswith('@@'):
                # @@ -10,7 +10,8 @@ 형태에서 정보 추출
                return line.strip()
        return ""

    @staticmethod
    def run_gh(args: List[str]) -> str:
        """gh CLI를 호출하고 stdout을 문자열로 반환한다."""
        result = subprocess.run(
            ["gh"] + args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        
        if result.returncode != 0:
            error_msg = result.stderr.strip()
            raise GitHubAPIError(f"gh CLI 오류: {error_msg}")
        
        return result.stdout.strip()

    def get_repo_info(self) -> Dict[str, str]:
        """현재 repo의 owner, name 을 gh CLI로 조회한다."""
        try:
            owner = self.run_gh(["repo", "view", "--json", "owner", "-q", ".owner.login"])
            name = self.run_gh(["repo", "view", "--json", "name", "-q", ".name"])
            return {"owner": owner, "name": name}
        except GitHubAPIError as e:
            raise GitHubAPIError(
                "현재 디렉터리가 Git 저장소가 아니거나 GitHub 인증이 필요합니다. "
                "'gh auth login'을 실행하고 Git 저장소 내에서 앱을 실행하세요."
            ) from e

    def get_my_pr_list(self, state: str = "all") -> List[Dict[str, Any]]:
        """
        내가 생성한 PR 목록을 gh CLI로 조회한다 (기본 정보만).

        Args:
            state: "open", "closed", "merged", "all"

        Returns:
            PR 정보 리스트 (number, title, url, state, createdAt)
        """
        output = self.run_gh([
            "pr", "list",
            "--author", "@me",
            "--state", state,
            "--json", "number,title,url,state,createdAt",
        ])
        if not output:
            return []
        
        import json
        prs = json.loads(output)
        return prs

    def get_my_pr_numbers(self, state: str = "all") -> List[int]:
        """
        내가 생성한 PR 번호 목록을 gh CLI로 조회한다.

        Args:
            state: "open", "closed", "merged", "all"

        Returns:
            PR 번호 리스트
        """
        prs = self.get_my_pr_list(state)
        return [pr["number"] for pr in prs]

    def get_comments_for_pr(
        self,
        owner: str,
        name: str,
        number: int,
        include_resolved: bool = False
    ) -> Dict[str, Any]:
        """
        단일 PR(number)에 대해 PR 메타 정보 + review comment 목록을 반환한다.

        Args:
            owner: Repository owner
            name: Repository name
            number: PR 번호
            include_resolved: True이면 resolved 코멘트도 포함

        Returns:
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
                  "bodyHTML": "<p>...</p>...",
                  "isResolved": false
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
                state
                createdAt
                author {
                  login
                }
                reviewThreads(first: 100) {
                  nodes {
                    isResolved
                    comments(first: 100) {
                      nodes {
                        id
                        databaseId
                        url
                        path
                        diffHunk
                        bodyHTML
                        createdAt
                        author {
                          login
                          url
                          avatarUrl
                        }
                      }
                    }
                  }
                }
                commits(first: 100) {
                  nodes {
                    commit {
                      abbreviatedOid
                      messageHeadline
                      committedDate
                      author {
                        name
                        user {
                          login
                          url
                          avatarUrl
                        }
                      }
                      url
                    }
                  }
                }
              }
            }
          }
        """

        raw = self.run_gh([
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
            is_resolved = thread.get("isResolved", False)
            
            # include_resolved가 False이고 resolved인 경우 스킵
            if not include_resolved and is_resolved:
                continue

            nodes = thread.get("comments", {}).get("nodes", []) or []
            
            # 첫 번째 코멘트가 원래 리뷰, 나머지는 댓글(replies)
            if not nodes:
                continue
            
            # 첫 번째 코멘트 (원래 리뷰)
            first_comment = nodes[0]
            author = first_comment.get("author") or {}
            diff_hunk = first_comment.get("diffHunk") or ""
            
            # diff hunk를 마지막 10줄만 보여주기 (코멘트가 달린 라인 주위) - 최적화
            if diff_hunk and '\n' in diff_hunk:
                lines = diff_hunk.split('\n')
                line_count = len(lines)
                if line_count > 10:
                    diff_hunk = '... (위 생략됨)\n' + '\n'.join(lines[-10:])
            
            # 파일 경로와 라인 번호 추출
            path = first_comment.get("path") or ""
            line_info = self._extract_line_info(diff_hunk) if diff_hunk else ""
            
            # 나머지 코멘트들을 댓글로 처리 - 최적화
            replies = []
            if len(nodes) > 1:
                for reply_comment in nodes[1:]:
                    reply_author = reply_comment.get("author")
                    if reply_author:
                        replies.append({
                            "id": reply_comment.get("id"),
                            "bodyHTML": reply_comment.get("bodyHTML"),
                            "createdAt": reply_comment.get("createdAt"),
                            "author": reply_author.get("login"),
                            "authorUrl": reply_author.get("url"),
                            "avatarUrl": reply_author.get("avatarUrl"),
                        })
            
            comments.append({
                "id": first_comment.get("id"),
                "databaseId": first_comment.get("databaseId"),
                "url": first_comment.get("url"),
                "path": path,
                "diffHunk": diff_hunk,
                "lineInfo": line_info,
                "author": author.get("login"),
                "authorUrl": author.get("url"),
                "avatarUrl": author.get("avatarUrl"),
                "bodyHTML": first_comment.get("bodyHTML"),
                "createdAt": first_comment.get("createdAt"),
                "isResolved": is_resolved,
                "replies": replies,
            })

        # 코멘트를 시간 최신순으로 정렬 (createdAt 기준 내림차순) - itemgetter로 최적화
        if comments:
            comments.sort(key=itemgetter("createdAt"), reverse=True)

        # 커밋 목록 처리
        commits = []
        commit_nodes = pr.get("commits", {}).get("nodes", []) or []
        for commit_node in commit_nodes:
            commit = commit_node.get("commit", {})
            author_info = commit.get("author", {})
            user_info = author_info.get("user") or {}
            
            commits.append({
                "abbreviatedOid": commit.get("abbreviatedOid"),
                "messageHeadline": commit.get("messageHeadline"),
                "committedDate": commit.get("committedDate"),
                "authorName": author_info.get("name"),
                "authorLogin": user_info.get("login"),
                "authorUrl": user_info.get("url"),
                "avatarUrl": user_info.get("avatarUrl"),
                "url": commit.get("url"),
            })

        # 커밋을 시간 최신순으로 정렬 (committedDate 기준 내림차순) - itemgetter로 최적화
        if commits:
            commits.sort(key=itemgetter("committedDate"), reverse=True)

        return {
            "number": number,
            "title": pr.get("title"),
            "url": pr.get("url"),
            "state": pr.get("state"),
            "createdAt": pr.get("createdAt"),
            "author": pr.get("author", {}).get("login"),
            "comments": comments,
            "commits": commits,
        }

    def get_all_comments(
        self,
        state: str = "all",
        include_resolved: bool = False
    ) -> List[Dict[str, Any]]:
        """
        내가 작성한 모든 PR의 리뷰 코멘트를 조회한다.

        Args:
            state: PR 상태 ("open", "closed", "merged", "all")
            include_resolved: True이면 resolved 코멘트도 포함

        Returns:
            코멘트가 있는 PR 목록
        """
        repo = self.get_repo_info()
        owner = repo["owner"]
        name = repo["name"]

        pr_numbers = self.get_my_pr_numbers(state=state)

        prs_with_comments: List[Dict[str, Any]] = []

        for pr_number in pr_numbers:
            pr_data = self.get_comments_for_pr(
                owner, name, pr_number, include_resolved=include_resolved
            )
            if not pr_data:
                continue
            if not pr_data.get("comments"):
                continue

            prs_with_comments.append(pr_data)

        return prs_with_comments

    def add_reply_to_comment(
        self,
        owner: str,
        name: str,
        pr_number: int,
        comment_id: str,
        body: str
    ) -> Dict[str, Any]:
        """
        리뷰 코멘트에 답글을 작성한다.

        Args:
            owner: 저장소 소유자
            name: 저장소 이름
            pr_number: PR 번호
            comment_id: 답글을 달 원본 코멘트 ID (databaseId, 숫자)
            body: 답글 내용

        Returns:
            생성된 답글 정보
        """
        # comment_id가 숫자 문자열인지 확인
        if not comment_id.isdigit():
            raise GitHubAPIError(f"comment_id는 숫자 형식이어야 합니다. 받은 값: {comment_id}")
        
        # 정수로 변환
        comment_id_int = int(comment_id)
        
        endpoint = f"repos/{owner}/{name}/pulls/{pr_number}/comments"
        
        # -F 플래그로 정수 타입 전달
        raw = self.run_gh([
            "api",
            endpoint,
            "-X", "POST",
            "-f", f"body={body}",
            "-F", f"in_reply_to={comment_id_int}",
        ])
        
        return json.loads(raw)
