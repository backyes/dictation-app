"""
LLM 服务封装模块
负责调用大模型 API 进行：
1. 从用户输入文本中提取目标单词清单
2. 为错误单词生成例句和记忆方法
3. 为单词生成中文释义和例句

支持多种提供商：Anthropic、OpenAI、OpenRouter、DeepSeek、LongCat、Ollama 等
"""
import logging
import time
from datetime import datetime
from database import get_active_provider, update_word_meaning, get_words_without_meanings
from llm_providers import create_provider
from logger import add_log, add_llm_trace

logger = logging.getLogger(__name__)


def _trace_llm_request(operation, model, success, message, request_data=None, response_data=None, elapsed=None):
    """记录 LLM 请求追踪"""
    add_llm_trace(operation, model, success, message, request_data, response_data, elapsed)


def get_active_client():
    """获取当前激活的 LLM 提供商客户端"""
    provider_config = get_active_provider()
    if not provider_config:
        raise Exception("没有配置 LLM 提供商，请先在设置页面添加并激活一个提供商")

    # 支持 api_key 或 auth_token 认证
    if not provider_config.get('api_key') and not provider_config.get('auth_token'):
        raise Exception(f"提供商 [{provider_config['name']}] 未设置 API Key 或 Auth Token")

    logger.info(f"使用 LLM 提供商: {provider_config['name']} (model={provider_config.get('model')})")
    return create_provider(provider_config)


def extract_words_from_text(text: str) -> list:
    """
    从用户输入的文本中提取目标单词清单
    支持多种格式：逗号分隔、换行分隔、编号列表等
    """
    logger.info(f"开始提取单词，输入文本长度: {len(text)} 字符")
    start = time.time()
    client = get_active_client()
    model = client.config.get('model', 'unknown') if hasattr(client, 'config') else 'unknown'

    # 记录 prompt
    prompt_preview = text[:100] + '...' if len(text) > 100 else text
    logger.info(f"LLM Prompt (extract_words): {prompt_preview}")
    add_log('info', 'llm_service', f'提取单词 Prompt: {prompt_preview}')

    try:
        words = client.extract_words(text)
        elapsed = int((time.time() - start) * 1000)
        logger.info(f"提取完成，共 {len(words)} 个单词: {words[:10]}{'...' if len(words) > 10 else ''}")
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
    """
    为错误单词生成例句和记忆方法
    返回: {'example': '...', 'memory_tip': '...', 'translation': '...'}
    """
    logger.info(f"为单词 [{word}] 生成学习提示")
    start = time.time()
    client = get_active_client()
    model = client.config.get('model', 'unknown') if hasattr(client, 'config') else 'unknown'

    # 记录 prompt
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
    """
    为单词生成中文释义、例句和音标
    返回: {'meaning': '中文释义', 'example': '例句', 'phonetic': '音标'}
    """
    logger.info(f"为单词 [{word}] 生成释义、例句和音标")
    start = time.time()
    client = get_active_client()
    model = client.config.get('model', 'unknown') if hasattr(client, 'config') else 'unknown'

    prompt = f"""请为英语单词 "{word}" 生成：
1. 中文释义（简洁准确）
2. 一个简短的英文例句（适合中学生水平），并将目标单词替换为 "______"（6个下划线）
3. 例句的中文翻译
4. 国际音标（IPA）

    # 记录 prompt
    add_log('info', 'llm_service', f'生成释义 Prompt: word={word}')

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
        import re

        logger.debug(f"LLM 响应: {response[:200]}...")

        # 解析 JSON
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
            logger.info(f"  ✅ {w['word']}: {result['meaning'][:20]}..., phonetic={result.get('phonetic', '')}")
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

        logger.info(f"测试 LLM 连接: {provider_config.get('name')} (model={provider_config.get('model')})")
        client = create_provider(provider_config)
        result = client.test_connection()
        elapsed = int((time.time() - start) * 1000)

        _trace_llm_request('test_connection', provider_config.get('model', 'unknown'),
            result['success'], result['message'],
            request_data={'provider': provider_config.get('name')},
            elapsed=elapsed)

        if result['success']:
            logger.info(f"连接测试成功: {result['message']}")
        else:
            logger.error(f"连接测试失败: {result['message']}")

        return result
    except Exception as e:
        elapsed = int((time.time() - start) * 1000)
        _trace_llm_request('test_connection',
            provider_config.get('model', 'unknown') if provider_config else 'unknown',
            False, str(e), elapsed=elapsed)
        logger.error(f"连接测试异常: {str(e)}")
        return {'success': False, 'message': f'连接失败: {str(e)}', 'model': provider_config.get('model', '')}


def generate_passage(words: list, difficulty: str = 'intermediate', custom_prompt: str = None, wrong_words: list = None, theme: str = '', theme_label: str = '') -> dict:
    """
    基于词库单词生成短文，帮助学生记忆单词
    """
    logger.info(f"生成短文，使用 {len(words)} 个单词，主题: {theme_label}")
    start = time.time()
    client = get_active_client()
    model = client.config.get('model', 'unknown') if hasattr(client, 'config') else 'unknown'

    # 选择单词：确保至少30%来自高频错误词汇，总共15-20个单词
    max_words = 20
    if wrong_words and len(wrong_words) > 0:
        min_wrong = max(3, int(max_words * 0.3))
        selected_wrong = wrong_words[:min_wrong + 2]
        remaining = [w for w in words if w not in selected_wrong]
        needed_regular = max_words - len(selected_wrong)
        selected_regular = remaining[:needed_regular] if needed_regular > 0 else []
        selected_words = selected_wrong + selected_regular
    else:
        selected_words = words[:max_words] if len(words) > max_words else words

    word_list = ', '.join(selected_words)
    wrong_list = ', '.join(wrong_words[:10]) if wrong_words else ''

    result = {
        'title': '',
        'title_cn': '',
        'content': '',
        'translation': '',
        'words_used': []
    }

    try:
        import re
        
        # Step 1: 生成英文短文
        story_prompt = f"""Write a short English story (300-400 words) about "{theme_label}" for KET-level learners.

Words to include (bold with **word**): {word_list}
Error words (use ≥3 times each): {wrong_list}

RULES:
- Start DIRECTLY with the story
- NO thinking, NO planning, NO reasoning, NO explanation
- Fun and simple grammar
- Output ONLY the story, nothing else"""

        logger.info(f"生成短文 Prompt: {len(story_prompt)} 字符")
        
        response = client.chat([
            {"role": "user", "content": story_prompt}
        ], temperature=0.7)

        logger.debug(f"LLM 响应长度: {len(response)} 字符")
        logger.debug(f"LLM 响应内容:\n{response}")

        # 提取故事内容（排除 thinking）
        paragraphs = re.split(r'\n\n+', response)
        story_parts = []
        story_started = False
        
        for p in paragraphs:
            p = p.strip()
            if len(p) < 30:
                continue
            
            # 检测 thinking 模式
            is_thinking = bool(re.match(r'^(I need|I\'ll|I will|I\'ve|I\'m going to|Let me|Okay|So I|First|The theme|The error|I should|I can|This is|Word count|I\'ll make|I\'ll write|I\'ll create|I\'ll ensure|I\'ll need|I\'ll incorporate|I\'ll use|I\'ll count|I\'ll craft|I\'ll plan|I\'ve crafted|I\'ll need to|I\'ll have to|I should|Let\'s)', p, re.IGNORECASE))
            is_thinking = is_thinking or bool(re.search(r'(?:must include|error words|at least 3 times|theme is|simple narrative|incorporating all|weave them|fun and simple|word count|KET level)', p, re.IGNORECASE))
            
            # 检测元评论/规划内容（不是故事本身）
            is_meta = bool(re.match(r'^[-*]\s+\w+:', p))  #  bullet points like "- quarter:"
            is_meta = is_meta or bool(re.search(r'\d+\s+uses?,?\s+need\s+\d+', p))  # "2 uses, need 3"
            is_meta = is_meta or bool(re.search(r'(?:map out|frequency count|mentally|naturally fit)', p, re.IGNORECASE))
            
            if is_thinking or is_meta:
                continue
            
            # 检测实际故事开始
            if not story_started:
                if re.match(r'^[A-Z][a-z]+(?:\s+[a-z]+)*\s+(?:was|is|had|found|went|saw|said|looked|opened|read|walked|ran|asked|told|gave|made|took|came|started|began|decided|wanted|liked|loved|helped|visited|worked|lived|played|talked|thought|remembered|wrote|received|bought|sold|cooked|ate|drank|wore|brought|carried|held|kept|left|returned|moved|changed|grew|built|cleaned|washed|baked|planted|picked|pulled|pushed|turned|closed|showed|explained|described|answered|replied|laughed|smiled|cried|shouted|whispered|danced|sang|listened|watched|waited|stopped|tried|continued|finished|completed|prepared|organized|arranged|collected|gathered|joined|attended|enjoyed|celebrated|welcomed|thanked|apologized|invited|allowed|encouraged|supported|recommended|suggested|promised|agreed|refused|accepted|believed|hoped|wished|dreamed|imagined|wondered|discovered|learned|understood|realized|noticed|recognized|forgot|guessed|predicted|expected|surprised|worried|feared|hated|disliked|embarrassed|confused|frustrated|disappointed|excited|interested|bored|tired|sick|healthy|strong|weak|happy|sad|angry|scared|proud|jealous|grateful|lonely|comfortable|patient|polite|friendly|kind|generous|honest|brave|clever|smart|foolish|careful|careless|curious|creative|energetic|gentle|responsible|serious|silly|strict|thoughtful|understanding|wise)\b', p):
                    story_started = True
                elif re.match(r'^"[^"]*"', p):
                    story_started = True
                elif re.match(r'^(?:Once|One day|That day|Yesterday|Today|Last|Next|In the|At the|On a|There was|It was|Every|This|My)', p, re.IGNORECASE):
                    story_started = True
            
            if story_started:
                story_parts.append(p)
        
        if not story_parts:
            # Fallback: 取最长的段落
            filtered = [p for p in paragraphs if len(p.strip()) > 100]
            if filtered:
                story_parts = [max(filtered, key=len)]
        
        content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', '\n\n'.join(story_parts)) if story_parts else response
        result['content'] = content

        # Step 2: 生成中文翻译
        if content:
            plain_text = re.sub(r'<[^>]+>', '', content)
            try:
                trans_response = client.chat([
                    {"role": "user", "content": f"Translate this English story to Chinese. Output ONLY the translation:\n\n{plain_text}"}
                ], temperature=0.3)
                
                trans_text = trans_response.strip()
                # 移除可能的 thinking
                trans_paragraphs = re.split(r'\n\n+', trans_text)
                trans_parts = []
                for tp in trans_paragraphs:
                    tp = tp.strip()
                    if tp and not re.match(r'^(I need|I\'ll|I will|I\'ve|Let me|Okay|So I|I should|I can|I\'ll translate|I\'ll provide|The translation)', tp, re.IGNORECASE):
                        trans_parts.append(tp)
                
                result['translation'] = '\n\n'.join(trans_parts) if trans_parts else trans_text
            except Exception as e:
                logger.error(f"翻译失败: {e}")

        # 提取实际使用的单词
        if result['content']:
            content_lower = result['content'].lower()
            result['words_used'] = [w for w in selected_words if w.lower() in content_lower]

        elapsed = int((time.time() - start) * 1000)
        logger.info(f"短文生成完成: {len(result['content'])} 字符, {len(result['words_used'])} 单词")

        _trace_llm_request('generate_passage', model, True,
            f"生成短文: {len(result['content'])} 字符, {len(result['words_used'])} 单词",
            request_data={'words': selected_words[:5]},
            response_data={'content_length': len(result['content']), 'word_count': len(result['words_used'])},
            elapsed=elapsed)

        return result

    except Exception as e:
        elapsed = int((time.time() - start) * 1000)
        _trace_llm_request('generate_passage', model, False, str(e),
            request_data={'words': selected_words},
            elapsed=elapsed)
        logger.error(f"短文生成失败: {str(e)}")
        raise Exception(f"短文生成失败: {str(e)}")
