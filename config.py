"""애플리케이션 설정"""

import os


class Config:
    """기본 설정"""
    
    # Flask 설정
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")
    DEBUG = os.environ.get("FLASK_DEBUG", "True").lower() in ("true", "1", "yes")
    HOST = os.environ.get("FLASK_HOST", "127.0.0.1")
    PORT = int(os.environ.get("FLASK_PORT", "5000"))
    
    # GitHub 관련 설정
    DEFAULT_PR_STATE = "open"  # "open", "closed", "merged", "all"
    DEFAULT_INCLUDE_RESOLVED = False  # resolved 코멘트 포함 여부
    
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
