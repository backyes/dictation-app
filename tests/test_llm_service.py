"""
LLM 服务模块单元测试
测试大模型连通性、单词提取、提示生成等功能
"""
import os
import sys
import unittest
from unittest.mock import patch, MagicMock, PropertyMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm_providers import AnthropicProvider, OpenAIProvider, create_provider, PROVIDER_PRESETS
from logger import add_log, add_llm_trace, get_logs, get_traces, clear_logs, clear_traces


class TestLogger(unittest.TestCase):
    """测试日志模块"""

    def setUp(self):
        clear_logs()
        clear_traces()

    def test_add_log(self):
        """测试添加日志"""
        log = add_log('info', 'test', '测试消息', {'key': 'value'})
        self.assertEqual(log['level'], 'INFO')
        self.assertEqual(log['module'], 'test')
        self.assertEqual(log['message'], '测试消息')
        self.assertEqual(log['data'], {'key': 'value'})

    def test_add_log_levels(self):
        """测试不同日志级别"""
        add_log('info', 'test', 'info消息')
        add_log('error', 'test', 'error消息')
        add_log('warn', 'test', 'warn消息')
        add_log('debug', 'test', 'debug消息')

        logs = get_logs()
        self.assertEqual(len(logs), 4)

    def test_get_logs_with_filter(self):
        """测试日志过滤"""
        add_log('info', 'module1', '消息1')
        add_log('error', 'module2', '消息2')
        add_log('info', 'module1', '消息3')

        info_logs = get_logs(level='info')
        self.assertEqual(len(info_logs), 2)

        module1_logs = get_logs(module='module1')
        self.assertEqual(len(module1_logs), 2)

    def test_add_llm_trace(self):
        """测试添加 LLM 追踪"""
        trace = add_llm_trace('test', 'test-model', True, '测试追踪',
                              request_data={'prompt': 'test'},
                              response_data={'text': 'response'},
                              elapsed=100)
        self.assertEqual(trace['operation'], 'test')
        self.assertEqual(trace['model'], 'test-model')
        self.assertTrue(trace['success'])
        self.assertEqual(trace['elapsed'], 100)

    def test_get_traces(self):
        """测试获取追踪列表"""
        for i in range(5):
            add_llm_trace('test', 'model', True, f'追踪{i}')

        traces = get_traces(limit=3)
        self.assertEqual(len(traces), 3)


class TestAnthropicProvider(unittest.TestCase):
    """测试 Anthropic 提供商"""

    def test_get_client_kwargs_with_api_key(self):
        """测试使用 api_key 创建客户端参数"""
        config = {
            'api_key': 'sk-test123',
            'base_url': 'https://api.anthropic.com',
            'model': 'claude-sonnet-4-20250514'
        }
        provider = AnthropicProvider(config)
        kwargs = provider._get_client_kwargs()

        self.assertEqual(kwargs['api_key'], 'sk-test123')
        self.assertEqual(kwargs['base_url'], 'https://api.anthropic.com')

    def test_get_client_kwargs_with_auth_token(self):
        """测试使用 auth_token 创建客户端参数（LongCat 模式）"""
        config = {
            'auth_token': 'ak_test_token',
            'base_url': 'https://api.longcat.chat/anthropic',
            'model': 'LongCat-2.0'
        }
        provider = AnthropicProvider(config)
        kwargs = provider._get_client_kwargs()

        # auth_token 应该作为 api_key 传递
        self.assertEqual(kwargs['api_key'], 'ak_test_token')
        self.assertEqual(kwargs['base_url'], 'https://api.longcat.chat/anthropic')

    def test_get_client_kwargs_no_auth(self):
        """测试无认证信息时抛出异常"""
        config = {'model': 'test'}
        provider = AnthropicProvider(config)

        with self.assertRaises(ValueError) as ctx:
            provider._get_client_kwargs()
        self.assertIn('未配置 API 认证信息', str(ctx.exception))

    @patch.object(AnthropicProvider, '_get_client_kwargs', return_value={'api_key': 'test'})
    @patch('anthropic.Anthropic')
    def test_chat_success(self, mock_anthropic, mock_kwargs):
        """测试成功调用 chat"""
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(type='text', text='Hello World')
        ]
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        config = {'api_key': 'sk-test', 'model': 'test', 'max_tokens': 1024, 'temperature': 0.7}
        provider = AnthropicProvider(config)
        result = provider.chat([{'role': 'user', 'content': 'Hi'}])

        self.assertEqual(result, 'Hello World')
        mock_client.messages.create.assert_called_once()

    @patch.object(AnthropicProvider, '_get_client_kwargs', return_value={'api_key': 'test'})
    @patch('anthropic.Anthropic')
    def test_chat_with_thinking(self, mock_anthropic, mock_kwargs):
        """测试处理 thinking 类型响应"""
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(type='thinking', thinking='Let me think...', text=None),
            MagicMock(type='text', text='Final answer')
        ]
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        config = {'api_key': 'sk-test', 'model': 'test'}
        provider = AnthropicProvider(config)
        result = provider.chat([{'role': 'user', 'content': 'Hi'}])

        self.assertEqual(result, 'Final answer')

    @patch.object(AnthropicProvider, '_get_client_kwargs', return_value={'api_key': 'test'})
    @patch('anthropic.Anthropic')
    def test_test_connection_success(self, mock_anthropic, mock_kwargs):
        """测试连接成功"""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(type='text', text='OK')]
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        config = {'api_key': 'sk-test', 'model': 'test-model'}
        provider = AnthropicProvider(config)
        result = provider.test_connection()

        self.assertTrue(result['success'])
        self.assertIn('OK', result['message'])

    @patch.object(AnthropicProvider, '_get_client_kwargs', return_value={'api_key': 'test'})
    @patch('anthropic.Anthropic')
    def test_test_connection_failure(self, mock_anthropic, mock_kwargs):
        """测试连接失败"""
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception('Connection error')
        mock_anthropic.return_value = mock_client

        config = {'api_key': 'sk-test', 'model': 'test-model'}
        provider = AnthropicProvider(config)
        result = provider.test_connection()

        self.assertFalse(result['success'])
        self.assertIn('Connection error', result['message'])


class TestOpenAIProvider(unittest.TestCase):
    """测试 OpenAI 提供商"""

    @patch('llm_providers.requests.post')
    def test_chat_success(self, mock_post):
        """测试成功调用 chat"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'choices': [{'message': {'content': 'Hello from OpenAI'}}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        config = {
            'api_key': 'sk-test',
            'model': 'gpt-4o-mini',
            'base_url': 'https://api.openai.com/v1',
            'max_tokens': 1024,
            'temperature': 0.7
        }
        provider = OpenAIProvider(config)
        result = provider.chat([{'role': 'user', 'content': 'Hi'}])

        self.assertEqual(result, 'Hello from OpenAI')

    @patch('llm_providers.requests.post')
    def test_test_connection_success(self, mock_post):
        """测试连接成功"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'choices': [{'message': {'content': 'OK'}}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        config = {
            'api_key': 'sk-test',
            'model': 'gpt-4o-mini',
            'base_url': 'https://api.openai.com/v1'
        }
        provider = OpenAIProvider(config)
        result = provider.test_connection()

        self.assertTrue(result['success'])


class TestProviderFactory(unittest.TestCase):
    """测试提供商工厂"""

    def test_create_anthropic_provider(self):
        """测试创建 Anthropic 提供商"""
        config = {'provider_type': 'anthropic', 'api_key': 'test'}
        provider = create_provider(config)
        self.assertIsInstance(provider, AnthropicProvider)

    def test_create_openai_provider(self):
        """测试创建 OpenAI 提供商"""
        config = {'provider_type': 'openai', 'api_key': 'test'}
        provider = create_provider(config)
        self.assertIsInstance(provider, OpenAIProvider)

    def test_create_unknown_provider_raises(self):
        """测试未知提供商类型抛出异常"""
        config = {'provider_type': 'unknown'}
        with self.assertRaises(ValueError):
            create_provider(config)


class TestProviderPresets(unittest.TestCase):
    """测试提供商预设"""

    def test_all_presets_have_required_fields(self):
        """测试所有预设都有必要字段"""
        required_fields = ['name', 'default_base_url', 'default_model', 'provider_type']
        for key, preset in PROVIDER_PRESETS.items():
            for field in required_fields:
                self.assertIn(field, preset, f"Preset '{key}' missing field '{field}'")

    def test_anthropic_preset(self):
        """测试 Anthropic 预设"""
        preset = PROVIDER_PRESETS['anthropic']
        self.assertEqual(preset['provider_type'], 'anthropic')
        self.assertIn('api.anthropic.com', preset['default_base_url'])

    def test_longcat_preset(self):
        """测试 LongCat 预设"""
        preset = PROVIDER_PRESETS['longcat']
        self.assertEqual(preset['provider_type'], 'openai')
        self.assertIn('longcat.chat', preset['default_base_url'])


class TestExtractWords(unittest.TestCase):
    """测试单词提取功能"""

    def setUp(self):
        clear_logs()

    @patch('llm_providers.AnthropicProvider.chat')
    def test_extract_words_from_text(self, mock_chat):
        """测试从文本提取单词"""
        mock_chat.return_value = '{"words": ["apple", "banana", "cherry"]}'

        config = {'api_key': 'test', 'model': 'test'}
        provider = AnthropicProvider(config)
        words = provider.extract_words('apple, banana, cherry')

        self.assertEqual(words, ['apple', 'banana', 'cherry'])

    @patch('llm_providers.AnthropicProvider.chat')
    def test_extract_words_lowercase(self, mock_chat):
        """测试提取单词转小写"""
        mock_chat.return_value = '{"words": ["APPLE", "Banana"]}'

        config = {'api_key': 'test', 'model': 'test'}
        provider = AnthropicProvider(config)
        words = provider.extract_words('APPLE, Banana')

        self.assertEqual(words, ['apple', 'banana'])

    @patch('llm_providers.AnthropicProvider.chat')
    def test_extract_words_deduplication(self, mock_chat):
        """测试提取单词去重"""
        mock_chat.return_value = '{"words": ["apple", "apple", "banana"]}'

        config = {'api_key': 'test', 'model': 'test'}
        provider = AnthropicProvider(config)
        words = provider.extract_words('apple, apple, banana')

        self.assertEqual(words, ['apple', 'banana'])


class TestGenerateHint(unittest.TestCase):
    """测试提示生成功能"""

    @patch('llm_providers.AnthropicProvider.chat')
    def test_generate_hint(self, mock_chat):
        """测试生成学习提示"""
        mock_chat.return_value = '''{
            "translation": "苹果",
            "example": "I eat an apple.",
            "example_translation": "我吃了一个苹果。",
            "memory_tip": "a-pple 像苹果"
        }'''

        config = {'api_key': 'test', 'model': 'test'}
        provider = AnthropicProvider(config)
        hint = provider.generate_hint('apple')

        self.assertEqual(hint['translation'], '苹果')
        self.assertEqual(hint['example'], 'I eat an apple.')
        self.assertEqual(hint['memory_tip'], 'a-pple 像苹果')


if __name__ == '__main__':
    unittest.main(verbosity=2)
