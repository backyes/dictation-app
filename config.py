import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dictation-app-secret-key')
    DATABASE_PATH = os.environ.get('DATABASE_PATH', os.path.join(os.path.dirname(__file__), 'instance', 'dictation.db'))

    # LLM Configuration
    ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
    ANTHROPIC_AUTH_TOKEN = os.environ.get('ANTHROPIC_AUTH_TOKEN', '')
    LLM_MODEL = os.environ.get('LLM_MODEL', 'LongCat-2.0')
    LLM_MAX_TOKENS = int(os.environ.get('LLM_MAX_TOKENS', '1024'))
    LLM_TEMPERATURE = float(os.environ.get('LLM_TEMPERATURE', '0.7'))
    # 优先使用 ANTHROPIC_BASE_URL，兼容 LLM_BASE_URL
    LLM_BASE_URL = os.environ.get('ANTHROPIC_BASE_URL', os.environ.get('LLM_BASE_URL', ''))

    @classmethod
    def validate(cls):
        """验证必要的配置"""
        if not cls.ANTHROPIC_API_KEY and not cls.ANTHROPIC_AUTH_TOKEN:
            raise ValueError(
                "请配置 ANTHROPIC_API_KEY 或 ANTHROPIC_AUTH_TOKEN 环境变量。\n"
                "复制 .env.example 为 .env 并填入你的 API 凭证。"
            )
