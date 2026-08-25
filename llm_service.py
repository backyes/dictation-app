"""
短文生成服务 - 鲁棒性重构 v6
核心改进：通过prompt约束让LLM直接输出可用内容，简化后端处理
"""
import logging
import time
import re
from database import get_active_provider, update_word_meaning, get_words_without_meanings
from llm_providers import create_provider, LLMResponse
from logger import add_log, add_llm_trace

logger = logging.getLogger(__name__)


class PassageGenerationError(Exception):
    pass


class OutputCleaner:
    """输出清洗器 - 简化版，主要做兜底处理"""
    
    ANNOTATION_PATTERN = r'\(\d+\)|\([A-Z]\)'
    
    @classmethod
    def clean_annotations(cls, text: str) -> str:
        """清除标注符号"""
        return re.sub(cls.ANNOTATION_PATTERN, '', text)
    
    @classmethod
    def extract_story(cls, response: str) -> str:
        """从响应中提取故事内容 - 简化版"""
        paragraphs = [p.strip() for p in re.split(r'\n\n+', response) if p.strip()]
        
        if not paragraphs:
            return response
        
        # 简单过滤明显的规划内容
        story_parts = []
        for p in paragraphs:
            # 跳过太短的段落
            if len(p) < 20:
                continue
            # 跳过编号列表开头
            if re.match(r'^\d+\.\s+[A-Z]', p):
                continue
            # 跳过 Step-by-Step 等标题
            if re.match(r'^(?:Step|Drafting|Brainstorm|Deconstruct|Plot|Character|Outline|Plan)\b', p, re.IGNORECASE):
                continue
            story_parts.append(p)
        
        if not story_parts:
            # Fallback: 取最长的段落
            filtered = [p for p in paragraphs if len(p) > 100]
            if filtered:
                story_parts = [max(filtered, key=len)]
            else:
                story_parts = [max(paragraphs, key=len)]
        
        return '\n\n'.join(story_parts)


class PassageGenerator:
    """短文生成器"""
    
    MAX_RETRIES = 3
    
    def __init__(self):
        self.client = None
        self.model = None
        self.debug_info = []
    
    def _get_client(self):
        if not self.client:
            provider_config = get_active_provider()
            if not provider_config:
                raise PassageGenerationError("没有配置 LLM 提供商")
            self.client = create_provider(provider_config)
            self.model = self.client.config.get('model', 'unknown')
        return self.client
    
    def _select_words(self, words: list, wrong_words: list) -> list:
        """选择单词 - 控制在8-10个"""
        max_words = 10
        if wrong_words and len(wrong_words) > 0:
            min_wrong = max(3, int(max_words * 0.3))
            selected_wrong = wrong_words[:min_wrong + 1]
            remaining = [w for w in words if w not in selected_wrong]
            needed_regular = max_words - len(selected_wrong)
            selected_regular = remaining[:needed_regular] if needed_regular > 0 else []
            return selected_wrong + selected_regular
        return words[:max_words] if len(words) > max_words else words
    
    def _build_story_prompt(self, theme_label: str, word_list: str, wrong_list: str) -> str:
        """构建故事生成 prompt - 添加严格约束"""
        return f"""Write a short English story (200-300 words) about "{theme_label}" for KET-level learners.

Words to include: {word_list}
Important words (use at least 3 times each): {wrong_list}

STRICT OUTPUT REQUIREMENTS:
1. Output MUST be a readable story with characters, dialogue, and descriptions
2. Start DIRECTLY with the story - first word must be a character name or "Once" or "One day"
3. Do NOT include ANY of the following:
   - Planning or thinking (e.g., "Let me plan...", "I need to include...")
   - Word frequency counts (e.g., "quarter: 3 times", "diary (2 uses)")
   - Annotations or markers (e.g., "(1)", "(2)", "(M)")
   - Numbered lists (e.g., "1. ", "2. ", "3. ")
   - Section headers (e.g., "Step-by-Step", "Drafting", "Brainstorming")
   - Character planning (e.g., "Tom: An old explorer")
   - Bullet points (e.g., "- quarter: ...")
4. The output should be directly readable and suitable for web display
5. Bold each target word like **word**
6. End naturally with the story conclusion

Output ONLY the story text, nothing else."""
    
    def _build_translation_prompt(self, story_text: str) -> str:
        """构建翻译 prompt"""
        return f"""Translate this English story to Chinese. Output ONLY the translation.

{story_text}"""
    
    def _generate_with_retry(self, prompt: str, temperature: float = 0.7, 
                              max_tokens: int = 2000) -> LLMResponse:
        """带重试的生成"""
        client = self._get_client()
        
        for attempt in range(self.MAX_RETRIES):
            try:
                response = client.chat(
                    [{"role": "user", "content": prompt}],
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                if response and len(response.content) > 50:
                    self.debug_info.append({
                        'attempt': attempt + 1,
                        'prompt': response.prompt[:500] if response.prompt else '',
                        'thinking': response.thinking[:1000] if response.thinking else '',
                        'content': response.content[:2000] if response.content else '',
                        'tokens': response.tokens,
                        'model': response.model,
                    })
                    return response
                logger.warning(f"生成响应太短，重试 {attempt + 1}/{self.MAX_RETRIES}")
            except Exception as e:
                logger.error(f"生成失败，重试 {attempt + 1}/{self.MAX_RETRIES}: {e}")
                if attempt == self.MAX_RETRIES - 1:
                    raise
        
        raise PassageGenerationError("生成失败，已达最大重试次数")
    
    def generate(self, words: list, wrong_words: list, theme_label: str) -> dict:
        """生成短文的完整流程"""
        start_time = time.time()
        self.debug_info = []
        
        # 1. 选择单词
        selected_words = self._select_words(words, wrong_words)
        word_list = ', '.join(selected_words)
        wrong_list = ', '.join(wrong_words[:10]) if wrong_words else ''
        
        logger.info(f"开始生成短文，主题: {theme_label}, 单词数: {len(selected_words)}")
        
        # 2. 生成英文故事
        story_prompt = self._build_story_prompt(theme_label, word_list, wrong_list)
        raw_response = self._generate_with_retry(story_prompt, temperature=0.7)
        
        logger.debug(f"原始响应:\n{raw_response.content}")
        
        # 3. 提取和清洗故事内容（简化版）
        story_text = OutputCleaner.extract_story(raw_response.content)
        story_text = OutputCleaner.clean_annotations(story_text)
        
        # 4. 格式化处理
        formatted_story = self._format_story(story_text, selected_words)
        
        # 5. 生成中文翻译
        translation = self._translate_story(story_text)
        
        # 6. 提取实际使用的单词
        words_used = [w for w in selected_words if w.lower() in story_text.lower()]
        
        elapsed = int((time.time() - start_time) * 1000)
        logger.info(f"短文生成完成: {len(story_text)} 字符, {len(words_used)} 单词, 耗时: {elapsed}ms")
        
        return {
            'title': '',
            'content': formatted_story,
            'translation': translation,
            'words_used': words_used,
            'debug_info': self.debug_info,
        }
    
    def _format_story(self, story_text: str, words: list) -> str:
        """格式化处理"""
        formatted = story_text
        for word in words:
            pattern = r'\b' + re.escape(word) + r'\b'
            formatted = re.sub(pattern, f'**{word}**', formatted, flags=re.IGNORECASE)
        formatted = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', formatted)
        formatted = formatted.replace('\n\n', '<br><br>')
        return formatted
    
    def _translate_story(self, story_text: str) -> str:
        """生成中文翻译"""
        try:
            prompt = self._build_translation_prompt(story_text)
            response = self._generate_with_retry(prompt, temperature=0.3, max_tokens=1500)
            
            translation = response.content.strip()
            translation = OutputCleaner.clean_annotations(translation)
            
            return translation
        except Exception as e:
            logger.error(f"翻译失败: {e}")
            return ''


# ==================== 兼容旧接口 ====================

def _trace_llm_request(operation, model, success, message, request_data=None, response_data=None, elapsed=None):
    add_llm_trace(operation, model, success, message, request_data, response_data, elapsed)


def get_active_client():
    provider_config = get_active_provider()
    if not provider_config:
        raise Exception("没有配置 LLM 提供商")
    if not provider_config.get('api_key') and not provider_config.get('auth_token'):
        raise Exception(f"提供商 [{provider_config['name']}] 未设置 API Key 或 Auth Token")
    return create_provider(provider_config)


def extract_words_from_text(text: str) -> list:
    logger.info(f"开始提取单词，输入文本长度: {len(text)} 字符")
    start = time.time()
    client = get_active_client()
    model = client.config.get('model', 'unknown') if hasattr(client, 'config') else 'unknown'
    
    prompt_preview = text[:100] + '...' if len(text) > 100 else text
    logger.info(f"LLM Prompt (extract_words): {prompt_preview}")
    
    try:
        words = client.extract_words(text)
        elapsed = int((time.time() - start) * 1000)
        _trace_llm_request('extract_words', model, True,
            f"提取 {len(words)} 个单词",
            request_data={'text_length': len(text)},
            response_data={'word_count': len(words), 'words': words[:20]},
            elapsed=elapsed)
        return words
    except Exception as e:
        elapsed = int((time.time() - start) * 1000)
        _trace_llm_request('extract_words', model, False, str(e),
            request_data={'text_length': len(text)},
            elapsed=elapsed)
        raise


def generate_hint_for_word(word: str) -> dict:
    logger.info(f"为单词 [{word}] 生成学习提示")
    start = time.time()
    client = get_active_client()
    model = client.config.get('model', 'unknown') if hasattr(client, 'config') else 'unknown'
    
    try:
        hint = client.generate_hint(word)
        elapsed = int((time.time() - start) * 1000)
        _trace_llm_request('generate_hint', model, True,
            f"生成 [{word}] 学习提示",
            request_data={'word': word},
            response_data={'translation': hint.get('translation', '')[:50]},
            elapsed=elapsed)
        return hint
    except Exception as e:
        elapsed = int((time.time() - start) * 1000)
        _trace_llm_request('generate_hint', model, False, str(e),
            request_data={'word': word},
            elapsed=elapsed)
        raise


def generate_meaning_for_word(word: str) -> dict:
    logger.info(f"为单词 [{word}] 生成释义、例句和音标")
    start = time.time()
    client = get_active_client()
    model = client.config.get('model', 'unknown') if hasattr(client, 'config') else 'unknown'
    
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
        import json
        
        try:
            result = json.loads(response.content)
        except json.JSONDecodeError:
            json_match = re.search(r'\{[^}]+\}', response.content, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
            else:
                result = {'meaning': '', 'example': '', 'example_translation': '', 'phonetic': ''}
        
        meaning = result.get('meaning', '')
        example = result.get('example', '')
        phonetic = result.get('phonetic', '')
        elapsed = int((time.time() - start) * 1000)
        
        _trace_llm_request('generate_meaning', model, True,
            f"生成 [{word}] 释义",
            request_data={'word': word},
            response_data={'meaning': meaning[:50], 'phonetic': phonetic},
            elapsed=elapsed)
        
        return {
            'meaning': meaning,
            'example': example,
            'example_translation': result.get('example_translation', ''),
            'phonetic': phonetic
        }
    except Exception as e:
        elapsed = int((time.time() - start) * 1000)
        _trace_llm_request('generate_meaning', model, False, str(e),
            request_data={'word': word},
            elapsed=elapsed)
        raise Exception(f"生成释义失败: {str(e)}")


def batch_generate_meanings():
    words = get_words_without_meanings()
    if not words:
        return {'processed': 0, 'success': 0, 'failed': 0}
    
    results = {'processed': len(words), 'success': 0, 'failed': 0}
    
    for w in words:
        try:
            result = generate_meaning_for_word(w['word'])
            update_word_meaning(w['id'], result['meaning'], result['example'], result.get('phonetic', ''))
            results['success'] += 1
        except Exception as e:
            results['failed'] += 1
            logger.error(f"  ❌ {w['word']}: {str(e)}")
    
    return results


def test_connection(provider_config: dict = None) -> dict:
    start = time.time()
    try:
        if provider_config is None:
            provider_config = get_active_provider()
            if not provider_config:
                return {'success': False, 'message': '没有配置 LLM 提供商', 'model': ''}
        
        client = create_provider(provider_config)
        result = client.test_connection()
        elapsed = int((time.time() - start) * 1000)
        
        _trace_llm_request('test_connection', provider_config.get('model', 'unknown'),
            result['success'], result['message'],
            request_data={'provider': provider_config.get('name')},
            elapsed=elapsed)
        
        return result
    except Exception as e:
        elapsed = int((time.time() - start) * 1000)
        _trace_llm_request('test_connection',
            provider_config.get('model', 'unknown') if provider_config else 'unknown',
            False, str(e), elapsed=elapsed)
        return {'success': False, 'message': f'连接失败: {str(e)}', 'model': provider_config.get('model', '')}


def generate_passage(words: list, difficulty: str = 'intermediate', custom_prompt: str = None,
                     wrong_words: list = None, theme: str = '', theme_label: str = '') -> dict:
    """基于词库单词生成短文"""
    generator = PassageGenerator()
    return generator.generate(words, wrong_words or [], theme_label)
