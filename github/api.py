"""GitHub CLI 및 GraphQL API 래퍼"""

import json
import subprocess
from typing import List, Dict, Any, Optional
from operator import itemgetter
from flask import current_app

from app.exceptions import GitHubAPIError


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
        # 설정에서 PR 목록 제한 가져오기
        pr_limit = 100
        try:
            if current_app:
                pr_limit = current_app.config.get("MAX_PR_LIST_LIMIT", 100)
        except RuntimeError:
            pass
        
        # gh CLI는 --limit 옵션으로 제한 가능 (기본값 30)
        args = [
            "pr", "list",
            "--author", "@me",
            "--state", state,
            "--json", "number,title,url,state,createdAt",
        ]
        
        # 제한값이 기본값(30)보다 크면 --limit 옵션 추가
        if pr_limit > 30:
            args.extend(["--limit", str(pr_limit)])
        
        output = self.run_gh(args)
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

    def get_current_user_login(self) -> str:
        """
        현재 인증된 사용자의 로그인 이름을 조회한다.

        Returns:
            사용자 로그인 이름
        """
        try:
            login = self.run_gh(["api", "user", "-q", ".login"])
            return login
        except GitHubAPIError:
            # 대체 방법: auth status에서 사용자 정보 가져오기
            try:
                status_output = self.run_gh(["auth", "status", "--json", "user", "-q", ".user.login"])
                return status_output
            except:
                raise GitHubAPIError("사용자 정보를 조회할 수 없습니다. 'gh auth login'을 실행하세요.")

    def get_prs_with_my_review_comments(self, state: str = "open") -> List[Dict[str, Any]]:
        """
        내가 리뷰 코멘트를 남긴 PR 목록을 조회한다.

        Args:
            state: "open", "closed", "merged", "all" (기본값: "open")

        Returns:
            PR 정보 리스트 (number, title, url, state, createdAt)
        """
        repo = self.get_repo_info()
        owner = repo["owner"]
        name = repo["name"]
        
        # 현재 사용자 로그인 이름 가져오기
        my_login = self.get_current_user_login()
        
        # 모든 OPEN PR 목록 조회
        if state == "all":
            pr_state = "all"
        elif state == "merged":
            # merged는 별도로 처리 필요
            pr_state = "all"
        else:
            pr_state = state
        
        # 설정에서 PR 목록 제한 가져오기
        pr_limit = 100
        try:
            if current_app:
                pr_limit = current_app.config.get("MAX_PR_LIST_LIMIT", 100)
        except RuntimeError:
            pass
        
        # gh CLI는 --limit 옵션으로 제한 가능 (기본값 30)
        args = [
            "pr", "list",
            "--state", pr_state,
            "--json", "number,title,url,state,createdAt,headRefName",
        ]
        
        # 제한값이 기본값(30)보다 크면 --limit 옵션 추가
        if pr_limit > 30:
            args.extend(["--limit", str(pr_limit)])
        
        output = self.run_gh(args)
        
        if not output:
            return []
        
        all_prs = json.loads(output)
        
        # merged 상태 필터링 (필요한 경우)
        if state == "merged":
            all_prs = [pr for pr in all_prs if pr.get("state") == "MERGED"]
        elif state == "open":
            all_prs = [pr for pr in all_prs if pr.get("state") == "OPEN"]
        elif state == "closed":
            all_prs = [pr for pr in all_prs if pr.get("state") == "CLOSED"]
        
        # 각 PR에 대해 내가 리뷰 코멘트를 남겼는지 확인
        prs_with_my_comments = []
        
        for pr in all_prs:
            pr_number = pr["number"]
            
            # GraphQL로 해당 PR의 리뷰 코멘트 조회
            # 설정에서 제한값 가져오기 (없으면 기본값 100 사용)
            max_threads = 100
            max_comments = 100
            try:
                if current_app:
                    max_threads = current_app.config.get("MAX_REVIEW_THREADS", 100)
                    max_comments = current_app.config.get("MAX_COMMENTS_PER_THREAD", 100)
            except RuntimeError:
                # 애플리케이션 컨텍스트 외부에서는 기본값 사용
                pass
            
            query = f"""
              query($owner: String!, $name: String!, $number: Int!) {{
                repository(owner: $owner, name: $name) {{
                  pullRequest(number: $number) {{
                    reviewThreads(first: {max_threads}) {{
                      nodes {{
                        comments(first: {max_comments}) {{
                          nodes {{
                            author {{
                              login
                            }}
                          }}
                        }}
                      }}
                    }}
                  }}
                }}
              }}
            """
            
            try:
                raw = self.run_gh([
                    "api", "graphql",
                    "-f", f"owner={owner}",
                    "-f", f"name={name}",
                    "-F", f"number={pr_number}",
                    "-f", f"query={query}",
                ])
                
                data = json.loads(raw)
                threads = (
                    data.get("data", {})
                    .get("repository", {})
                    .get("pullRequest", {})
                    .get("reviewThreads", {})
                    .get("nodes", [])
                )
                
                # 내가 작성한 코멘트가 있는지 확인
                has_my_comment = False
                for thread in threads:
                    comments = thread.get("comments", {}).get("nodes", [])
                    for comment in comments:
                        author_login = comment.get("author", {}).get("login", "")
                        if author_login == my_login:
                            has_my_comment = True
                            break
                    if has_my_comment:
                        break
                
                if has_my_comment:
                    prs_with_my_comments.append(pr)
                    
            except GitHubAPIError:
                # 에러가 발생하면 해당 PR은 스킵
                continue
        
        return prs_with_my_comments

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

        # 설정에서 제한값 가져오기 (없으면 기본값 100 사용)
        max_threads = 100
        max_comments = 100
        max_commits = 100
        try:
            if current_app:
                max_threads = current_app.config.get("MAX_REVIEW_THREADS", 100)
                max_comments = current_app.config.get("MAX_COMMENTS_PER_THREAD", 100)
                max_commits = current_app.config.get("MAX_COMMITS", 100)
        except RuntimeError:
            # 애플리케이션 컨텍스트 외부에서는 기본값 사용
            pass
        
        query = f"""
          query($owner: String!, $name: String!, $number: Int!) {{
            repository(owner: $owner, name: $name) {{
              pullRequest(number: $number) {{
                number
                title
                url
                state
                createdAt
                author {{
                  login
                }}
                reviewThreads(first: {max_threads}) {{
                  nodes {{
                    isResolved
                    comments(first: {max_comments}) {{
                      nodes {{
                        id
                        databaseId
                        url
                        path
                        diffHunk
                        bodyHTML
                        createdAt
                        author {{
                          login
                          url
                          avatarUrl
                        }}
                      }}
                    }}
                  }}
                }}
                commits(first: {max_commits}) {{
                  nodes {{
                    commit {{
                      abbreviatedOid
                      messageHeadline
                      committedDate
                      author {{
                        name
                        user {{
                          login
                          url
                          avatarUrl
                        }}
                      }}
                      url
                    }}
                  }}
                }}
              }}
            }}
          }}
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
