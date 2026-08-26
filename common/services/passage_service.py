"""
Passage generation service - platform-agnostic core logic.
This module is shared between Web (Flask) and Android (Flet) platforms.
"""
import logging
import time
import json
import re
from typing import Generator, Dict, Any, Optional

logger = logging.getLogger(__name__)


def generate_passage_stream(
    words: list,
    wrong_words: list = None,
    difficulty: str = 'intermediate',
    provider_config: dict = None,
    storage = None
) -> Generator[Dict[str, Any], None, None]:
    """
    Generate a passage with streaming LLM output.
    
    Args:
        words: List of words to include
        wrong_words: List of words with high error frequency
        difficulty: Difficulty level
        provider_config: LLM provider configuration
        storage: Storage instance for saving passages
        
    Yields:
        Dict with event types:
        - {'type': 'status', 'message': '...'}
        - {'type': 'debug_prompt', 'prompt': '...', 'model': '...'}
        - {'type': 'thinking_start'}
        - {'type': 'thinking', 'content': '...'}
        - {'type': 'text_start'}
        - {'type': 'text', 'content': '...'}
        - {'type': 'done', 'result': {...}}
        - {'type': 'error', 'message': '...'}
    """
    if wrong_words is None:
        wrong_words = []
    
    yield {'type': 'status', 'message': '准备生成参数...'}
    
    if not provider_config:
        yield {'type': 'error', 'message': '没有配置 LLM 提供商'}
        return
    
    if not words or len(words) < 3:
        yield {'type': 'error', 'message': '词库单词不足，请先添加至少3个单词'}
        return
    
    # Create LLM client
    from common.llm.providers import create_provider
    client = create_provider(provider_config)
    
    # Select words (max 10, with wrong words prioritized)
    max_words = 10
    selected_words = []
    if wrong_words and len(wrong_words) > 0:
        min_wrong = max(3, int(max_words * 0.3))
        selected_wrong = wrong_words[:min_wrong + 1]
        remaining = [w for w in words if w not in selected_wrong]
        needed_regular = max_words - len(selected_wrong)
        selected_regular = remaining[:needed_regular] if needed_regular > 0 else []
        selected_words = selected_wrong + selected_regular
    else:
        selected_words = words[:max_words] if len(words) > max_words else words
    
    # Build prompt
    word_list = ', '.join(selected_words)
    wrong_list = ', '.join(wrong_words[:5])
    
    prompt = f"""Write a short English story (150-200 words) about daily life for KET-level learners.

Words to include: {word_list}
Important words (use at least 2 times each): {wrong_list}

Use the words naturally in sentences.
Bold each target word like **word**.

Output ONLY this JSON:
{{"story":"Your story text with **bold** words","translation":"Chinese translation of the story"}}

No other text."""
    
    yield {
        'type': 'debug_prompt',
        'prompt': prompt,
        'model': provider_config.get('model', 'unknown'),
        'words': selected_words,
        'wrong_words': wrong_words
    }
    
    # Stream generation
    full_content = ''
    thinking_content = ''
    start_time = time.time()
    first_token_time = None
    token_count = 0
    
    yield {'type': 'status', 'message': '连接大模型...'}
    
    try:
        for event in client.chat_stream(
            [{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=4000
        ):
            if event['type'] == 'thinking_start':
                yield {'type': 'thinking_start'}
            elif event['type'] == 'thinking':
                thinking_content += event['content']
                yield {'type': 'thinking', 'content': event['content']}
            elif event['type'] == 'text_start':
                yield {'type': 'text_start'}
            elif event['type'] == 'text':
                full_content += event['content']
                token_count += 1
                if first_token_time is None:
                    first_token_time = time.time()
                yield {'type': 'text', 'content': event['content']}
            elif event['type'] == 'error':
                yield {'type': 'error', 'message': event['content']}
                return
        
        # Parse result
        story_text = _parse_json_response(full_content, 'story')
        translation = _parse_json_response(full_content, 'translation')
        formatted_story = _format_story(story_text, selected_words)
        words_used = [w for w in selected_words if w.lower() in story_text.lower()]
        
        # Save passage to storage
        passage_id = None
        if storage and story_text:
            try:
                passage_id = storage.add_passage(
                    title='',
                    content=formatted_story,
                    words_used=words_used,
                    difficulty=difficulty
                )
            except Exception as e:
                logger.warning(f"Failed to save passage: {e}")
        
        end_time = time.time()
        total_time = round(end_time - start_time, 2)
        ttft = round(first_token_time - start_time, 2) if first_token_time else None
        
        yield {
            'type': 'done',
            'result': {
                'id': passage_id,
                'content': formatted_story,
                'translation': translation,
                'words_used': words_used,
                'thinking': thinking_content,
                'debug': {
                    'prompt': prompt,
                    'model': provider_config.get('model', 'unknown'),
                    'raw_response': full_content,
                    'tokens': token_count,
                    'total_time': total_time,
                    'ttft': ttft,
                    'thinking_length': len(thinking_content),
                    'content_length': len(full_content),
                    'words_used': words_used,
                    'words': selected_words,
                    'difficulty': difficulty
                }
            }
        }
        
    except Exception as e:
        yield {'type': 'error', 'message': str(e)}


def _parse_json_response(text: str, key: str) -> str:
    """Parse JSON from LLM response"""
    if not text:
        return ''
    
    # Try direct JSON parse
    try:
        data = json.loads(text.strip())
        return data.get(key, '')
    except (json.JSONDecodeError, KeyError):
        pass
    
    # Try to extract JSON from text
    pattern = r'"' + key + r'"\s*:\s*"([^"]*(?:\\.[^"]*)*)"'
    matches = re.findall(pattern, text, re.DOTALL)
    if matches:
        result = matches[0]
        # Unescape JSON string
        try:
            result = json.loads('"' + result + '"')
        except:
            pass
        return result
    
    # Try broader JSON extraction
    try:
        json_start = text.find('{')
        json_end = text.rfind('}') + 1
        if json_start >= 0 and json_end > json_start:
            data = json.loads(text[json_start:json_end])
            return data.get(key, '')
    except:
        pass
    
    return ''


def _format_story(story_text: str, words: list) -> str:
    """Format story with bold words and paragraphs"""
    if not story_text:
        return ''
    
    # Bold target words
    for word in words:
        pattern = r'\*\*' + re.escape(word) + r'\*\*'
        story_text = re.sub(pattern, f'<strong>{word}</strong>', story_text, flags=re.IGNORECASE)
    
    # Clean up any remaining **
    story_text = story_text.replace('**', '')
    
    # Add paragraph breaks
    sentences = re.split(r'(?<=[.!?])\s+', story_text)
    paragraphs = []
    current_para = []
    
    for i, sentence in enumerate(sentences):
        current_para.append(sentence)
        # New paragraph every 3-4 sentences
        if len(current_para) >= 3 and (i + 1) % 3 == 0:
            paragraphs.append(' '.join(current_para))
            current_para = []
    
    if current_para:
        paragraphs.append(' '.join(current_para))
    
    return '\n\n'.join(paragraphs)
