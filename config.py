"""애플리케이션 설정"""

import os


class Config:
    """기본 설정"""
    
    # Flask 설정
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")
    DEBUG = os.environ.get("FLASK_DEBUG", "True").lower() in ("true", "1", "yes")
    HOST = os.environ.get("FLASK_HOST", "127.0.0.1")
    PORT = int(os.environ.get("FLASK_PORT", "5000"))
    
    # 데이터베이스 설정
    # 프로젝트 루트 디렉토리에 database.db 파일 생성
    basedir = os.path.abspath(os.path.dirname(__file__))
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        f"sqlite:///{os.path.join(basedir, 'database.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False  # 성능 최적화를 위해 False
    
    # GitHub 관련 설정
    DEFAULT_PR_STATE = "open"  # "open", "closed", "merged", "all"
    DEFAULT_INCLUDE_RESOLVED = False  # resolved 코멘트 포함 여부
    
    # GitHub API 제한 설정
    # GraphQL 쿼리에서 한 번에 가져올 수 있는 최대 개수
    MAX_REVIEW_THREADS = int(os.environ.get("MAX_REVIEW_THREADS", "100"))  # PR당 최대 리뷰 스레드 개수
    MAX_COMMENTS_PER_THREAD = int(os.environ.get("MAX_COMMENTS_PER_THREAD", "100"))  # 스레드당 최대 코멘트 개수
    MAX_COMMITS = int(os.environ.get("MAX_COMMITS", "100"))  # PR당 최대 커밋 개수
    
    # PR 목록 제한 (gh CLI는 기본적으로 30개 제한, 더 많은 경우 --limit 옵션 사용)
    MAX_PR_LIST_LIMIT = int(os.environ.get("MAX_PR_LIST_LIMIT", "100"))  # PR 목록 최대 개수
    
    # UI 설정
    APP_TITLE = "코드 리뷰 체커"
    COMMENTS_PER_PAGE = 50  # 페이지네이션 (향후 구현)


class DevelopmentConfig(Config):
    """개발 환경 설정"""
    DEBUG = True


class ProductionConfig(Config):
    """운영 환경 설정"""
    DEBUG = False
    SECRET_KEY = os.environ.get("SECRET_KEY")


# 환경별 설정 매핑
config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}


def get_config(env_name: str = None) -> Config:
    """환경 이름으로 설정 객체 반환"""
    if env_name is None:
        env_name = os.environ.get("FLASK_ENV", "default")
    return config_by_name.get(env_name, DevelopmentConfig)
