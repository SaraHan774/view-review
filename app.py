#!/usr/bin/env python3
"""
코드 리뷰 체커 - GitHub PR 리뷰 코멘트 조회 웹 애플리케이션
"""

from flask import Flask, render_template, request
from markupsafe import Markup
from datetime import datetime

from config import get_config
from github import GitHubAPI
from github.api import GitHubAPIError


def format_time(timestamp):
    """ISO 8601 시간을 사람이 읽기 쉬운 형태로 변환"""
    if not timestamp:
        return ""
    
    try:
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        now = datetime.now(dt.tzinfo)
        diff = now - dt
        
        if diff.days > 365:
            years = diff.days // 365
            return f"{years}년 전"
        elif diff.days > 30:
            months = diff.days // 30
            return f"{months}개월 전"
        elif diff.days > 0:
            return f"{diff.days}일 전"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours}시간 전"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes}분 전"
        else:
            return "방금 전"
    except:
        return timestamp[:10]  # 날짜만 반환


def create_app(config_name: str = None) -> Flask:
    """Flask 애플리케이션 팩토리"""
    app = Flask(__name__)
    
    # 설정 로드
    config = get_config(config_name)
    app.config.from_object(config)
    
    # Jinja2 필터 등록
    app.jinja_env.filters['format_time'] = format_time
    
    # 설정 로드
    config = get_config(config_name)
    app.config.from_object(config)
    
    # GitHub API 클라이언트 초기화
    github_api = GitHubAPI()
    
    @app.route("/")
    def index():
        """메인 페이지 - PR 목록"""
        # 쿼리 파라미터로 필터 옵션 받기
        state = request.args.get("state", config.DEFAULT_PR_STATE)
        
        try:
            # 저장소 정보 조회
            repo = github_api.get_repo_info()
            owner = repo["owner"]
            name = repo["name"]
            
            # PR 목록만 먼저 조회 (빠른 로딩)
            prs = github_api.get_my_pr_list(state=state)
            
            return render_template(
                "index.html",
                prs=prs,
                owner=owner,
                name=name,
                state=state,
                config=config,
            )
        
        except GitHubAPIError as e:
            # GitHub API 에러 처리
            return render_template(
                "error.html",
                error_title="GitHub 연결 오류",
                error_message=str(e),
                config=config,
            ), 500
        except Exception as e:
            # 기타 예상치 못한 에러
            return render_template(
                "error.html",
                error_title="오류 발생",
                error_message=f"예상치 못한 오류가 발생했습니다: {str(e)}",
                config=config,
            ), 500
    
    @app.route("/pr/<int:pr_number>")
    def pr_detail(pr_number):
        """PR 상세 페이지 - 리뷰 코멘트 표시"""
        include_resolved = request.args.get("include_resolved", "false").lower() == "true"
        compact_mode = request.args.get("compact_mode", "false").lower() == "true"
        
        try:
            repo = github_api.get_repo_info()
            owner = repo["owner"]
            name = repo["name"]
            
            # 해당 PR의 코멘트 조회
            pr_data = github_api.get_comments_for_pr(
                owner, name, pr_number, include_resolved=include_resolved
            )
            
            if not pr_data:
                return render_template(
                    "error.html",
                    error_title="PR을 찾을 수 없습니다",
                    error_message=f"PR #{pr_number}을(를) 찾을 수 없습니다.",
                    config=config,
                ), 404
            
            # bodyHTML을 Markup으로 래핑하여 안전하게 렌더링 (성능 최적화)
            comments = pr_data.get("comments", [])
            if comments:
                for comment in comments:
                    body = comment.get("bodyHTML")
                    comment["bodyHTML_safe"] = Markup(body) if body else Markup("")
                    # 댓글도 Markup 처리
                    replies = comment.get("replies")
                    if replies:
                        for reply in replies:
                            body = reply.get("bodyHTML")
                            if body:
                                reply["bodyHTML"] = Markup(body)
            
            return render_template(
                "pr_detail.html",
                pr=pr_data,
                owner=owner,
                name=name,
                include_resolved=include_resolved,
                compact_mode=compact_mode,
                config=config,
            )
        
        except GitHubAPIError as e:
            return render_template(
                "error.html",
                error_title="GitHub 연결 오류",
                error_message=str(e),
                config=config,
            ), 500
        except Exception as e:
            return render_template(
                "error.html",
                error_title="오류 발생",
                error_message=f"예상치 못한 오류가 발생했습니다: {str(e)}",
                config=config,
            ), 500
    
    @app.route("/pr/<int:pr_number>/reply", methods=["POST"])
    def add_reply(pr_number):
        """리뷰 코멘트에 답글 추가"""
        try:
            repo = github_api.get_repo_info()
            owner = repo["owner"]
            name = repo["name"]
            
            # 폼 데이터 가져오기
            comment_id = request.form.get("comment_id")
            body = request.form.get("body", "").strip()
            
            if not comment_id or not body:
                return {"success": False, "error": "comment_id와 body가 필요합니다."}, 400
            
            # 답글 작성
            github_api.add_reply_to_comment(
                owner=owner,
                name=name,
                pr_number=pr_number,
                comment_id=comment_id,
                body=body
            )
            
            return {"success": True}
        
        except GitHubAPIError as e:
            return {"success": False, "error": str(e)}, 500
        except Exception as e:
            return {"success": False, "error": f"예상치 못한 오류: {str(e)}"}, 500
    
    @app.route("/health")
    def health():
        """헬스체크 엔드포인트"""
        return {"status": "ok", "service": "code-review-checker"}
    
    return app


if __name__ == "__main__":
    app = create_app()
    app.run(
        host=app.config["HOST"],
        port=app.config["PORT"],
        debug=app.config["DEBUG"]
    )
