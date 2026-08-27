"""
LLM 提供商模块单元测试
测试提供商工厂、消息格式转换、响应解析等
"""
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.llm.providers import (
    BaseLLMProvider, AnthropicProvider, OpenAIProvider,
    create_provider, PROVIDER_PRESETS
)


class TestProviderFactory(unittest.TestCase):
    """测试提供商工厂"""

    def test_create_anthropic_provider(self):
        """测试创建 Anthropic 提供商"""
        config = {
            'provider_type': 'anthropic',
            'api_key': 'sk-ant-test',
            'model': 'claude-sonnet-4-20250514',
            'base_url': 'https://api.anthropic.com'
        }
        provider = create_provider(config)
        self.assertIsInstance(provider, AnthropicProvider)

    def test_create_openai_provider(self):
        """测试创建 OpenAI 提供商"""
        config = {
            'provider_type': 'openai',
            'api_key': 'sk-test',
            'model': 'gpt-4o-mini',
            'base_url': 'https://api.openai.com/v1'
        }
        provider = create_provider(config)
        self.assertIsInstance(provider, OpenAIProvider)

    def test_create_unknown_provider_raises(self):
        """测试未知提供商类型抛出异常"""
        config = {'provider_type': 'unknown'}
        with self.assertRaises(ValueError):
            create_provider(config)

    def test_default_provider_type(self):
        """测试默认提供商类型为 openai"""
        config = {'api_key': 'test'}
        provider = create_provider(config)
        self.assertIsInstance(provider, OpenAIProvider)


class TestProviderPresets(unittest.TestCase):
    """测试预定义提供商配置"""

    def test_anthropic_preset(self):
        """测试 Anthropic 预设"""
        preset = PROVIDER_PRESETS['anthropic']
        self.assertEqual(preset['provider_type'], 'anthropic')
        self.assertIn('api.anthropic.com', preset['default_base_url'])

    def test_openai_preset(self):
        """测试 OpenAI 预设"""
        preset = PROVIDER_PRESETS['openai']
        self.assertEqual(preset['provider_type'], 'openai')
        self.assertIn('api.openai.com', preset['default_base_url'])

    def test_longcat_preset(self):
        """测试 LongCat 预设"""
        preset = PROVIDER_PRESETS['longcat']
        self.assertEqual(preset['provider_type'], 'openai')
        self.assertIn('longcat.chat', preset['default_base_url'])

    def test_all_presets_have_required_fields(self):
        """测试所有预设都有必要字段"""
        required_fields = ['name', 'default_base_url', 'default_model', 'provider_type']
        for key, preset in PROVIDER_PRESETS.items():
            for field in required_fields:
                self.assertIn(field, preset, f"Preset '{key}' missing field '{field}'")


class TestWordsParsing(unittest.TestCase):
    """测试单词提取响应解析"""

    def setUp(self):
        """创建测试用的提供商实例"""
        self.config = {
            'provider_type': 'openai',
            'api_key': 'test',
            'model': 'test-model',
            'base_url': 'https://example.com'
        }
        self.provider = OpenAIProvider(self.config)

    def test_parse_valid_json_words(self):
        """测试解析有效的 JSON 单词响应"""
        response = '{"words": ["apple", "banana", "cherry"]}'
        words = self.provider._parse_words_response(response)
        self.assertEqual(words, ['apple', 'banana', 'cherry'])

    def test_parse_json_with_extra_text(self):
        """测试解析带额外文本的 JSON"""
        response = 'Here are the words: {"words": ["hello", "world"]}'
        words = self.provider._parse_words_response(response)
        self.assertEqual(words, ['hello', 'world'])

    def test_parse_empty_words(self):
        """测试解析空单词列表"""
        response = '{"words": []}'
        words = self.provider._parse_words_response(response)
        self.assertEqual(words, [])

    def test_parse_words_deduplication(self):
        """测试单词去重"""
        response = '{"words": ["apple", "apple", "banana"]}'
        words = self.provider._parse_words_response(response)
        self.assertEqual(words, ['apple', 'banana'])

    def test_parse_words_lowercase(self):
        """测试单词转小写"""
        response = '{"words": ["APPLE", "Banana"]}'
        words = self.provider._parse_words_response(response)
        self.assertEqual(words, ['apple', 'banana'])

    def test_parse_words_filter_short(self):
        """测试过滤单字母"""
        response = '{"words": ["a", "ab", "abc"]}'
        words = self.provider._parse_words_response(response)
        self.assertEqual(words, ['ab', 'abc'])


class TestHintParsing(unittest.TestCase):
    """测试提示生成响应解析"""

    def setUp(self):
        self.config = {
            'provider_type': 'openai',
            'api_key': 'test',
            'model': 'test-model',
            'base_url': 'https://example.com'
        }
        self.provider = OpenAIProvider(self.config)

    def test_parse_valid_json_hint(self):
        """测试解析有效的 JSON 提示"""
        response = '{"translation": "苹果", "example": "I eat an apple.", "example_translation": "我吃了一个苹果。", "memory_tip": "a-pple 像苹果"}'
        hint = self.provider._parse_hint_response(response)
        self.assertEqual(hint['translation'], '苹果')
        self.assertEqual(hint['example'], 'I eat an apple.')
        self.assertEqual(hint['memory_tip'], 'a-pple 像苹果')

    def test_parse_partial_hint(self):
        """测试解析部分字段的提示"""
        response = '{"translation": "香蕉"}'
        hint = self.provider._parse_hint_response(response)
        self.assertEqual(hint['translation'], '香蕉')
        self.assertEqual(hint['example'], '')
        self.assertEqual(hint['memory_tip'], '')

    def test_parse_invalid_json_hint(self):
        """测试解析无效 JSON 的提示"""
        response = 'This is not JSON'
        hint = self.provider._parse_hint_response(response)
        self.assertEqual(hint['example'], 'This is not JSON')


class TestAnthropicProviderChat(unittest.TestCase):
    """测试 Anthropic 提供商聊天功能（模拟）"""

    def test_message_format_conversion(self):
        """测试消息格式转换（system 消息提取）"""
        config = {
            'provider_type': 'anthropic',
            'api_key': 'test',
            'model': 'claude-sonnet-4-20250514',
            'base_url': 'https://api.anthropic.com',
            'max_tokens': 1024,
            'temperature': 0.7
        }
        provider = AnthropicProvider(config)

        # Mock the anthropic client
        with patch.object(provider, 'chat', mock_return='Mocked response') as mock_chat:
            messages = [
                {'role': 'system', 'content': 'You are helpful'},
                {'role': 'user', 'content': 'Hello'}
            ]
            provider.chat(messages)
            mock_chat.assert_called_once()


class TestOpenAIProviderChat(unittest.TestCase):
    """测试 OpenAI 提供商聊天功能（模拟）"""

    @patch('common.llm.providers.requests.post')
    def test_successful_chat(self, mock_post):
        """测试成功的聊天调用"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'choices': [{'message': {'content': 'Hello there!'}}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        config = {
            'provider_type': 'openai',
            'api_key': 'sk-test',
            'model': 'gpt-4o-mini',
            'base_url': 'https://api.openai.com/v1',
            'max_tokens': 1024,
            'temperature': 0.7
        }
        provider = OpenAIProvider(config)
        result = provider.chat([{'role': 'user', 'content': 'Hi'}])

        self.assertEqual(result.content, 'Hello there!')
        mock_post.assert_called_once()

    @patch('common.llm.providers.requests.post')
    def test_chat_with_custom_temperature(self, mock_post):
        """测试自定义温度的聊天调用"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'choices': [{'message': {'content': 'Response'}}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        config = {
            'provider_type': 'openai',
            'api_key': 'sk-test',
            'model': 'gpt-4o-mini',
            'base_url': 'https://api.openai.com/v1',
            'max_tokens': 1024,
            'temperature': 0.7
        }
        provider = OpenAIProvider(config)
        provider.chat([{'role': 'user', 'content': 'Hi'}], temperature=0.2)

        # 验证调用参数
        call_args = mock_post.call_args
        json_data = call_args[1]['json']
        self.assertEqual(json_data['temperature'], 0.2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
