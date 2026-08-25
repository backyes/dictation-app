"""
短文生成服务 - 鲁棒性重构
架构：生成 → 验证 → 清洗 → 翻译 → 后处理
"""
import logging
import time
import re
from typing import Optional
from database import get_active_provider, update_word_meaning, get_words_without_meanings
from llm_providers import create_provider
from logger import add_log, add_llm_trace

logger = logging.getLogger(__name__)


class PassageGenerationError(Exception):
    """短文生成异常"""
    pass


class OutputValidator:
    """输出验证器"""
    
    # Thinking 模式
    THINKING_PATTERNS = [
        r'^(I need|I\'ll|I will|I\'ve|I\'m going to|Let me|Okay|So I|First|'
        r'The theme|The error|I should|I can|This is|Word count|I\'ll make|'
        r'I\'ll write|I\'ll create|I\'ll ensure|I\'ll need|I\'ll incorporate|'
        r'I\'ll use|I\'ll count|I\'ll craft|I\'ll plan|I\'ve crafted|'
        r'I\'ll need to|I\'ll have to|Let\'s|I will|Let me think|I should)',
        r'(?:must include|error words|at least \d+ times|theme is|simple narrative|'
        r'incorporating all|weave them|fun and simple|word count|KET level)',
    ]
    
    # 元评论模式（词频统计、规划清单等）
    META_PATTERNS = [
        r'^[-*]\s+\w+:',                           # "- quarter:" 或 "* diary:"
        r'\d+\s+uses?,?\s+need\s+\d+',             # "2 uses, need 3"
        r'(?:map out|frequency count|mentally|naturally fit|'
        r'let me see|I need to make sure|I\'ll make sure)',
    ]
    
    # 标注模式 (1), (2), (M) 等
    ANNOTATION_PATTERN = r'\(\d+\)|\([A-Z]\)'
    
    @classmethod
    def is_thinking(cls, text: str) -> bool:
        """检测是否为 thinking 内容"""
        for pattern in cls.THINKING_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False
    
    @classmethod
    def is_meta_commentary(cls, text: str) -> bool:
        """检测是否为元评论/规划内容"""
        for pattern in cls.META_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False
    
    @classmethod
    def has_annotations(cls, text: str) -> bool:
        """检测是否包含标注符号"""
        return bool(re.search(cls.ANNOTATION_PATTERN, text))
    
    @classmethod
    def validate_story_output(cls, text: str) -> tuple[bool, str]:
        """
        验证故事输出是否合法
        返回: (是否合法, 原因)
        """
        if not text or len(text) < 100:
            return False, "输出太短"
        
        # 检查 thinking 比例
        paragraphs = [p.strip() for p in re.split(r'\n\n+', text) if p.strip()]
        if not paragraphs:
            return False, "无有效段落"
        
        thinking_count = sum(1 for p in paragraphs if cls.is_thinking(p))
        if thinking_count > len(paragraphs) * 0.3:
            return False, f"thinking 内容过多 ({thinking_count}/{len(paragraphs)})"
        
        # 检查元评论
        meta_count = sum(1 for p in paragraphs if cls.is_meta_commentary(p))
        if meta_count > 0:
            return False, f"包含 {meta_count} 次元评论"
        
        return True, "OK"
    
    @classmethod
    def clean_annotations(cls, text: str) -> str:
        """清除标注符号 (1), (2), (M) 等"""
        return re.sub(cls.ANNOTATION_PATTERN, '', text)


class StoryExtractor:
    """故事内容提取器"""
    
    # 故事开始的标志
    STORY_START_PATTERNS = [
        # 人物名 + 动词
        r'^[A-Z][a-z]+(?:\s+[a-z]+)*\s+(?:was|is|had|found|went|saw|said|looked|'
        r'opened|read|walked|ran|asked|told|gave|made|took|came|started|began|'
        r'decided|wanted|liked|loved|helped|visited|worked|lived|played|talked|'
        r'thought|remembered|wrote|received|bought|sold|cooked|ate|drank|wore|'
        r'brought|carried|held|kept|left|returned|moved|changed|grew|built|'
        r'cleaned|washed|baked|planted|picked|pulled|pushed|turned|closed|showed|'
        r'explained|described|answered|replied|laughed|smiled|cried|shouted|'
        r'whispered|danced|sang|listened|watched|waited|stopped|tried|continued|'
        r'finished|completed|prepared|organized|arranged|collected|gathered|'
        r'joined|attended|enjoyed|celebrated|welcomed|thanked|apologized|invited|'
        r'allowed|encouraged|supported|recommended|suggested|promised|agreed|'
        r'refused|accepted|believed|hoped|wished|dreamed|imagined|wondered|'
        r'discovered|learned|understood|realized|noticed|recognized|forgot|'
        r'guessed|predicted|expected|surprised|worried|feared|hated|disliked|'
        r'embarrassed|confused|frustrated|disappointed|excited|interested|bored|'
        r'tired|sick|healthy|strong|weak|happy|sad|angry|scared|proud|jealous|'
        r'grateful|lonely|comfortable|patient|polite|friendly|kind|generous|'
        r'honest|brave|clever|smart|foolish|careful|careless|curious|creative|'
        r'energetic|gentle|responsible|serious|silly|strict|thoughtful|'
        r'understanding|wise)\b',
        # 对话开始
        r'^"[^"]*"',
        # 场景描述开始
        r'^(?:Once|One day|That day|Yesterday|Today|Last|Next|In the|At the|'
        r'On a|There was|It was|Every|This|My|Every day|Every night|'
        r'Every morning|Every evening)',
    ]
    
    @classmethod
    def find_story_start(cls, paragraphs: list[str]) -> int:
        """找到故事开始的段落索引"""
        for i, p in enumerate(paragraphs):
            p = p.strip()
            if len(p) < 20:
                continue
            
            # 跳过 thinking 和元评论
            if OutputValidator.is_thinking(p) or OutputValidator.is_meta_commentary(p):
                continue
            
            # 检查是否符合故事开始模式
            for pattern in cls.STORY_START_PATTERNS:
                if re.match(pattern, p, re.IGNORECASE):
                    return i
        
        # 如果没找到，返回第一个非空段落
        for i, p in enumerate(paragraphs):
            if len(p.strip()) > 20:
                return i
        
        return 0
    
    @classmethod
    def extract_story(cls, response: str) -> str:
        """从响应中提取故事内容"""
        paragraphs = [p.strip() for p in re.split(r'\n\n+', response) if p.strip()]
        
        if not paragraphs:
            return response
        
        # 找到故事开始位置
        start_idx = cls.find_story_start(paragraphs)
        
        # 收集故事段落
        story_parts = []
        for p in paragraphs[start_idx:]:
            # 跳过 thinking 和元评论
            if OutputValidator.is_thinking(p) or OutputValidator.is_meta_commentary(p):
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
    """短文生成器 - 主类"""
    
    MAX_RETRIES = 3
    
    def __init__(self):
        self.client = None
        self.model = None
    
    def _get_client(self):
        """获取 LLM 客户端"""
        if not self.client:
            provider_config = get_active_provider()
            if not provider_config:
                raise PassageGenerationError("没有配置 LLM 提供商")
            self.client = create_provider(provider_config)
            self.model = self.client.config.get('model', 'unknown')
        return self.client
    
    def _select_words(self, words: list, wrong_words: list) -> list:
        """选择单词"""
        max_words = 20
        if wrong_words and len(wrong_words) > 0:
            min_wrong = max(3, int(max_words * 0.3))
            selected_wrong = wrong_words[:min_wrong + 2]
            remaining = [w for w in words if w not in selected_wrong]
            needed_regular = max_words - len(selected_wrong)
            selected_regular = remaining[:needed_regular] if needed_regular > 0 else []
            return selected_wrong + selected_regular
        return words[:max_words] if len(words) > max_words else words
    
    def _build_story_prompt(self, theme_label: str, word_list: str, wrong_list: str) -> str:
        """构建故事生成 prompt"""
        return f"""Write a short English story (300-400 words) about "{theme_label}" for KET-level learners.

Words to include (bold with **word**): {word_list}
Error words (use ≥3 times each): {wrong_list}

CRITICAL RULES:
1. Start DIRECTLY with the story - first word should be a character name or "Once" or "One day"
2. NO thinking, NO planning, NO reasoning, NO explanation before or after the story
3. NO word frequency counts, NO usage notes, NO annotations like (1) (2) (M)
4. NO bullet points, NO lists, NO meta-commentary
5. Fun and simple grammar suitable for KET-level learners
6. Output ONLY the story text, nothing else

Example of CORRECT output:
"Once upon a time, there was a young girl named Sarah. She worked as a waitress..."

Example of WRONG output:
"Let me plan this story first. I need to include these words..."
"- quarter: I will use this 3 times"
"Lucy is a waitress (1) at a restaurant"

Now write the story:"""
    
    def _build_translation_prompt(self, story_text: str) -> str:
        """构建翻译 prompt"""
        return f"""Translate this English story to Chinese. 
Output ONLY the translation, nothing else.
No annotations, no notes, no explanations.

English story:
{story_text}

Chinese translation:"""
    
    def _generate_with_retry(self, prompt: str, temperature: float = 0.7, 
                              max_tokens: int = 2000) -> str:
        """带重试的生成"""
        client = self._get_client()
        
        for attempt in range(self.MAX_RETRIES):
            try:
                response = client.chat(
                    [{"role": "user", "content": prompt}],
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                if response and len(response) > 50:
                    return response
                logger.warning(f"生成响应太短，重试 {attempt + 1}/{self.MAX_RETRIES}")
            except Exception as e:
                logger.error(f"生成失败，重试 {attempt + 1}/{self.MAX_RETRIES}: {e}")
                if attempt == self.MAX_RETRIES - 1:
                    raise
        
        raise PassageGenerationError("生成失败，已达最大重试次数")
    
    def generate(self, words: list, wrong_words: list, theme_label: str) -> dict:
        """
        生成短文的完整流程
        
        Returns:
            {
                'title': str,
                'content': str,  # HTML格式，生词加粗
                'translation': str,  # 中文翻译
                'words_used': list,  # 实际使用的单词
            }
        """
        start_time = time.time()
        
        # 1. 选择单词
        selected_words = self._select_words(words, wrong_words)
        word_list = ', '.join(selected_words)
        wrong_list = ', '.join(wrong_words[:10]) if wrong_words else ''
        
        logger.info(f"开始生成短文，主题: {theme_label}, 单词数: {len(selected_words)}")
        
        # 2. 生成英文故事
        story_prompt = self._build_story_prompt(theme_label, word_list, wrong_list)
        raw_story = self._generate_with_retry(story_prompt, temperature=0.7)
        
        # 3. 提取和清洗故事内容
        story_text = StoryExtractor.extract_story(raw_story)
        
        # 4. 清除标注符号
        story_text = OutputValidator.clean_annotations(story_text)
        
        # 5. 验证故事
        is_valid, reason = OutputValidator.validate_story_output(story_text)
        if not is_valid:
            logger.warning(f"故事验证失败: {reason}，尝试重新生成")
            # 重新生成一次
            raw_story = self._generate_with_retry(story_prompt, temperature=0.8)
            story_text = StoryExtractor.extract_story(raw_story)
            story_text = OutputValidator.clean_annotations(story_text)
        
        # 6. 格式化处理（加粗生词）
        formatted_story = self._format_story(story_text, selected_words)
        
        # 7. 生成中文翻译
        translation = self._translate_story(story_text)
        
        # 8. 提取实际使用的单词
        words_used = [w for w in selected_words if w.lower() in story_text.lower()]
        
        elapsed = int((time.time() - start_time) * 1000)
        logger.info(f"短文生成完成: {len(story_text)} 字符, {len(words_used)} 单词, 耗时: {elapsed}ms")
        
        return {
            'title': '',
            'content': formatted_story,
            'translation': translation,
            'words_used': words_used,
        }
    
    def _format_story(self, story_text: str, words: list) -> str:
        """格式化处理：加粗生词"""
        formatted = story_text
        for word in words:
            # 使用正则匹配完整单词（不区分大小写）
            pattern = r'\b' + re.escape(word) + r'\b'
            formatted = re.sub(pattern, f'**{word}**', formatted, flags=re.IGNORECASE)
        # 将 **word** 转换为 <strong>word</strong>
        formatted = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', formatted)
        # 转换换行为 <br>
        formatted = formatted.replace('\n\n', '<br><br>')
        return formatted
    
    def _translate_story(self, story_text: str) -> str:
        """生成中文翻译"""
        try:
            prompt = self._build_translation_prompt(story_text)
            translation = self._generate_with_retry(prompt, temperature=0.3, max_tokens=1500)
            
            # 清洗翻译
            translation = translation.strip()
            
            # 移除可能的 thinking
            paragraphs = [p.strip() for p in re.split(r'\n\n+', translation) if p.strip()]
            clean_paragraphs = []
            for p in paragraphs:
                if not OutputValidator.is_thinking(p) and not OutputValidator.is_meta_commentary(p):
                    clean_paragraphs.append(p)
            
            if clean_paragraphs:
                translation = '\n\n'.join(clean_paragraphs)
            
            # 清除标注
            translation = OutputValidator.clean_annotations(translation)
            
            return translation
        except Exception as e:
            logger.error(f"翻译失败: {e}")
            return ''


# ==================== 兼容旧接口 ====================

def _trace_llm_request(operation, model, success, message, request_data=None, response_data=None, elapsed=None):
    """记录 LLM 请求追踪"""
    add_llm_trace(operation, model, success, message, request_data, response_data, elapsed)


def get_active_client():
    """获取当前激活的 LLM 提供商客户端"""
    provider_config = get_active_provider()
    if not provider_config:
        raise Exception("没有配置 LLM 提供商，请先在设置页面添加并激活一个提供商")
    if not provider_config.get('api_key') and not provider_config.get('auth_token'):
        raise Exception(f"提供商 [{provider_config['name']}] 未设置 API Key 或 Auth Token")
    logger.info(f"使用 LLM 提供商: {provider_config['name']} (model={provider_config.get('model')})")
    return create_provider(provider_config)


def extract_words_from_text(text: str) -> list:
    """从用户输入的文本中提取目标单词清单"""
    logger.info(f"开始提取单词，输入文本长度: {len(text)} 字符")
    start = time.time()
    client = get_active_client()
    model = client.config.get('model', 'unknown') if hasattr(client, 'config') else 'unknown'
    
    prompt_preview = text[:100] + '...' if len(text) > 100 else text
    logger.info(f"LLM Prompt (extract_words): {prompt_preview}")
    add_log('info', 'llm_service', f'提取单词 Prompt: {prompt_preview}')
    
    try:
        words = client.extract_words(text)
        elapsed = int((time.time() - start) * 1000)
        logger.info(f"提取完成，共 {len(words)} 个单词")
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
    """为错误单词生成例句和记忆方法"""
    logger.info(f"为单词 [{word}] 生成学习提示")
    start = time.time()
    client = get_active_client()
    model = client.config.get('model', 'unknown') if hasattr(client, 'config') else 'unknown'
    
    logger.info(f"LLM Prompt (generate_hint): word={word}")
    add_log('info', 'llm_service', f'生成提示 Prompt: word={word}')
    
    try:
        hint = client.generate_hint(word)
        elapsed = int((time.time() - start) * 1000)
        logger.info(f"生成提示完成: translation={hint.get('translation', '')[:30]}...")
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
    """为单词生成中文释义、例句和音标"""
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
    
    add_log('info', 'llm_service', f'生成释义 Prompt: word={word}')
    
    try:
        response = client.chat([{"role": "user", "content": prompt}], temperature=0.3)
        import json
        
        logger.debug(f"LLM 响应: {response[:200]}...")
        
        try:
            result = json.loads(response)
        except json.JSONDecodeError:
            json_match = re.search(r'\{[^}]+\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
            else:
                result = {'meaning': '', 'example': '', 'example_translation': '', 'phonetic': ''}
        
        meaning = result.get('meaning', '')
        example = result.get('example', '')
        phonetic = result.get('phonetic', '')
        elapsed = int((time.time() - start) * 1000)
        logger.info(f"生成完成: meaning={meaning[:30]}..., phonetic={phonetic}")
        
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
        logger.error(f"生成释义失败: {str(e)}")
        raise Exception(f"生成释义失败: {str(e)}")


def batch_generate_meanings():
    """批量为没有释义的单词生成释义和例句"""
    words = get_words_without_meanings()
    if not words:
        logger.info("没有需要生成释义的单词")
        return {'processed': 0, 'success': 0, 'failed': 0}
    
    logger.info(f"开始批量生成释义，共 {len(words)} 个单词")
    results = {'processed': len(words), 'success': 0, 'failed': 0}
    
    for w in words:
        try:
            result = generate_meaning_for_word(w['word'])
            update_word_meaning(w['id'], result['meaning'], result['example'], result.get('phonetic', ''))
            results['success'] += 1
            logger.info(f"  ✅ {w['word']}: {result['meaning'][:20]}...")
        except Exception as e:
            results['failed'] += 1
            logger.error(f"  ❌ {w['word']}: {str(e)}")
    
    logger.info(f"批量生成完成: 成功 {results['success']}, 失败 {results['failed']}")
    return results


def test_connection(provider_config: dict = None) -> dict:
    """测试 LLM 服务连接"""
    start = time.time()
    try:
        if provider_config is None:
            provider_config = get_active_provider()
            if not provider_config:
                return {'success': False, 'message': '没有配置 LLM 提供商', 'model': ''}
        
        logger.info(f"测试 LLM 连接: {provider_config.get('name')}")
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
        logger.error(f"连接测试异常: {str(e)}")
        return {'success': False, 'message': f'连接失败: {str(e)}', 'model': provider_config.get('model', '')}


def generate_passage(words: list, difficulty: str = 'intermediate', custom_prompt: str = None,
                     wrong_words: list = None, theme: str = '', theme_label: str = '') -> dict:
    """
    基于词库单词生成短文
    """
    generator = PassageGenerator()
    return generator.generate(words, wrong_words or [], theme_label)
