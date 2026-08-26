"""Common LLM service layer"""
import logging
import time
import json
import re
from common.storage.sqlite_storage import get_storage

logger = logging.getLogger(__name__)


def get_active_client():
    """Get active LLM client"""
    from common.llm.providers import create_provider
    provider_config = get_storage().get_active_provider()
    if not provider_config:
        raise Exception("没有配置 LLM 提供商")
    if not provider_config.get('api_key') and not provider_config.get('auth_token'):
        raise Exception(f"提供商 [{provider_config['name']}] 未设置 API Key 或 Auth Token")
    return create_provider(provider_config)


def test_connection(provider_config=None):
    """Test LLM connection"""
    from common.llm.providers import create_provider
    start = time.time()
    try:
        if provider_config is None:
            provider_config = get_storage().get_active_provider()
            if not provider_config:
                return {'success': False, 'message': '没有配置 LLM 提供商', 'model': ''}
        client = create_provider(provider_config)
        result = client.test_connection()
        elapsed = int((time.time() - start) * 1000)
        return result
    except Exception as e:
        elapsed = int((time.time() - start) * 1000)
        return {'success': False, 'message': f'连接失败: {str(e)}', 'model': ''}


def extract_words_from_text(text: str) -> list:
    """Extract words from text using LLM"""
    logger.info(f"开始提取单词，输入文本长度: {len(text)} 字符")
    start = time.time()
    client = get_active_client()
    
    try:
        words = client.extract_words(text)
        elapsed = int((time.time() - start) * 1000)
        return words
    except Exception as e:
        elapsed = int((time.time() - start) * 1000)
        raise


def generate_passage(words: list, difficulty: str = 'intermediate', custom_prompt: str = None, wrong_words: list = None, theme: str = '', theme_label: str = '') -> dict:
    """Generate passage using LLM"""
    from common.llm.passage_generator import PassageGenerator
    generator = PassageGenerator()
    result = generator.generate(words, wrong_words or [], theme_label)
    return result


def batch_generate_meanings():
    """Batch generate meanings for words without them"""
    storage = get_storage()
    words = storage.get_words_without_meanings()
    if not words:
        return {'processed': 0, 'success': 0, 'failed': 0}
    
    results = {'processed': len(words), 'success': 0, 'failed': 0}
    for w in words:
        try:
            result = generate_meaning_for_word(w['word'])
            storage.update_word_meaning(w['id'], result['meaning'], result['example'], result.get('phonetic', ''))
            results['success'] += 1
        except Exception as e:
            results['failed'] += 1
            logger.error(f"  ❌ {w['word']}: {str(e)}")
    return results


def generate_meaning_for_word(word: str) -> dict:
    """Generate meaning for a single word"""
    client = get_active_client()
    prompt = f"""请为英语单词 "{word}" 生成：
1. 中文释义（简洁准确）
2. 一个简短的英文例句（适合中学生水平），并将目标单词替换为 "______"（6个下划线）
3. 例句的中文翻译
4. 国际音标（IPA）

请严格按照以下JSON格式返回，不要包含任何其他内容：
{{
  "meaning": "中文释义",
  "example": "英文例句，目标单词用______替代",
  "example_translation": "例句中文翻译",
  "phonetic": "/国际音标/"
}}"""
    
    try:
        response = client.chat([{"role": "user", "content": prompt}], temperature=0.3)
        try:
            result = json.loads(response.content)
        except json.JSONDecodeError:
            json_match = re.search(r'\{[^}]+\}', response.content, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
            else:
                result = {'meaning': '', 'example': '', 'example_translation': '', 'phonetic': ''}
        
        return {
            'meaning': result.get('meaning', ''),
            'example': result.get('example', ''),
            'example_translation': result.get('example_translation', ''),
            'phonetic': result.get('phonetic', '')
        }
    except Exception as e:
        raise Exception(f"生成释义失败: {str(e)}")
