"""Common passage generator"""
import logging
import time
import re
import json
from common.services.llm import get_active_client

logger = logging.getLogger(__name__)


class PassageGenerator:
    """Passage generator - JSON structured output"""
    
    MAX_RETRIES = 3
    
    def __init__(self):
        self.client = None
        self.model = None
        self.debug_info = []
    
    def _get_client(self):
        if not self.client:
            self.client = get_active_client()
            self.model = self.client.config.get('model', 'unknown')
        return self.client
    
    def _select_words(self, words: list, wrong_words: list) -> list:
        """Select words - control at 8-10"""
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
        """Build story generation prompt - force JSON output"""
        return f"""Write a short English story (150-200 words) about daily life for KET-level learners.

Words to include: {word_list}
Important words (use at least 2 times each): {wrong_list}

Use the words naturally in sentences.
Bold each target word like **word**.

Output ONLY this JSON:
{{"story":"Your story text with **bold** words","translation":"Chinese translation of the story"}}

No other text."""
    
    def _build_translation_prompt(self, story_text: str) -> str:
        """Build translation prompt - force JSON output"""
        return f"""Translate this English story to Chinese.

{story_text}

Output MUST be a valid JSON object:
{{"translation": "Your complete Chinese translation here"}}

Do NOT include any text outside the JSON object."""
    
    def _generate_with_retry(self, prompt: str, temperature: float = 0.7, max_tokens: int = 8000):
        """Generate with retry (non-streaming)"""
        client = self._get_client()
        
        for attempt in range(self.MAX_RETRIES):
            try:
                response = client.chat(
                    [{"role": "user", "content": prompt}],
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                if response and len(response.content) > 50:
                    return response
                logger.warning(f"Response too short, retry {attempt + 1}/{self.MAX_RETRIES}")
            except Exception as e:
                logger.error(f"Generation failed, retry {attempt + 1}/{self.MAX_RETRIES}: {e}")
                if attempt == self.MAX_RETRIES - 1:
                    raise
                max_tokens = int(max_tokens * 1.2)
        
        raise Exception("Generation failed, max retries reached")
    
    def _parse_json_response(self, content: str, key: str) -> str:
        """Extract value from JSON response"""
        if not content:
            return ''
        
        text = content.strip()
        
        try:
            data = json.loads(text)
            if key in data:
                return data[key].strip()
        except json.JSONDecodeError:
            pass
        
        json_match = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', text)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                if key in data:
                    return data[key].strip()
            except json.JSONDecodeError:
                pass
        
        json_match = re.search(r'\{[^{}]*"key"[^{}]*\}', text)
        if not json_match:
            json_match = re.search(r'\{[\s\S]*?"' + key + r'"[\s\S]*?\}', text)
        if json_match:
            try:
                data = json.loads(json_match.group())
                if key in data:
                    return data[key].strip()
            except json.JSONDecodeError:
                pass
        
        key_match = re.search(rf'"{key}"\s*:\s*"((?:[^"\\]|\\.)*)"', text, re.DOTALL)
        if key_match:
            value = key_match.group(1)
            value = value.replace('\\n', '\n').replace('\\"', '"').replace('\\\\', '\\')
            return value.strip()
        
        return text
    
    def generate(self, words: list, wrong_words: list, theme_label: str) -> dict:
        """Generate passage (non-streaming) - single call for story + translation"""
        start_time = time.time()
        self.debug_info = []
        
        selected_words = self._select_words(words, wrong_words)
        word_list = ', '.join(selected_words)
        wrong_list = ', '.join(wrong_words[:10]) if wrong_words else ''
        
        logger.info(f"Starting passage generation, words: {len(selected_words)}")
        
        # Single call generates both story and translation
        story_prompt = self._build_story_prompt(theme_label, word_list, wrong_list)
        raw_response = self._generate_with_retry(story_prompt, temperature=0.7, max_tokens=4000)
        
        story_text = self._parse_json_response(raw_response.content, 'story')
        translation = self._parse_json_response(raw_response.content, 'translation')
        
        if not story_text:
            raise Exception("Story generation failed - empty response")
        
        formatted_story = self._format_story(story_text, selected_words)
        
        words_used = [w for w in selected_words if w.lower() in story_text.lower()]
        
        elapsed = int((time.time() - start_time) * 1000)
        logger.info(f"Passage generation complete: {len(story_text)} chars, {len(words_used)} words, elapsed: {elapsed}ms")
        
        return {
            'title': '',
            'content': formatted_story,
            'translation': translation,
            'words_used': words_used,
            'debug_info': self.debug_info,
        }
    
    def _format_story(self, story_text: str, words: list) -> str:
        """Format story"""
        formatted = story_text
        for word in words:
            pattern = r'\b' + re.escape(word) + r'\b'
            formatted = re.sub(pattern, f'**{word}**', formatted, flags=re.IGNORECASE)
        formatted = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', formatted)
        formatted = formatted.replace('\n\n', '<br><br>')
        return formatted
    
    def _translate_story(self, story_text: str) -> str:
        """Generate Chinese translation"""
        try:
            prompt = self._build_translation_prompt(story_text)
            response = self._generate_with_retry(prompt, temperature=0.3, max_tokens=6000)
            translation = self._parse_json_response(response.content, 'translation')
            return translation
        except Exception as e:
            logger.error(f"Translation failed: {e}")
            return ''
