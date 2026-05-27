import unittest
from unittest.mock import MagicMock, patch, AsyncMock

from komitto.llm.openai_client import OpenAIClient
from komitto.llm.gemini_client import GeminiClient
from komitto.llm.anthropic_client import AnthropicClient

class TestLLMClients(unittest.IsolatedAsyncioTestCase):

    @patch('komitto.llm.openai_client.OpenAI')
    def test_openai_client_generate(self, mock_openai):
        # Setup mock
        mock_instance = MagicMock()
        mock_openai.return_value = mock_instance
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Commit message"))]
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 20
        mock_response.usage.total_tokens = 30
        
        mock_instance.chat.completions.create.return_value = mock_response

        # Test
        config = {"api_key": "test_key", "model": "gpt-4"}
        client = OpenAIClient(config)
        msg, usage = client.generate_commit_message("prompt")

        # Assertions
        self.assertEqual(msg, "Commit message")
        self.assertEqual(usage, {
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30
        })

    @patch('komitto.llm.openai_client.OpenAI')
    def test_openai_client_stream(self, mock_openai):
        # Setup mock
        mock_instance = MagicMock()
        mock_openai.return_value = mock_instance
        
        # Mock streaming chunks
        chunk1 = MagicMock()
        chunk1.choices = [MagicMock(delta=MagicMock(content="Hello ", reasoning_content=None))]
        chunk1.usage = None
        
        chunk2 = MagicMock()
        chunk2.choices = [MagicMock(delta=MagicMock(content="World", reasoning_content=None))]
        chunk2.usage = None
        
        chunk3 = MagicMock()
        chunk3.choices = []
        chunk3.usage.prompt_tokens = 5
        chunk3.usage.completion_tokens = 2
        chunk3.usage.total_tokens = 7
        
        mock_instance.chat.completions.create.return_value = iter([chunk1, chunk2, chunk3])

        # Test
        config = {"api_key": "test_key", "model": "gpt-4"}
        client = OpenAIClient(config)
        
        chunks = list(client.stream_commit_message("prompt"))
        
        # Assertions
        # Chunk 1
        self.assertEqual(chunks[0][0], "Hello ")
        self.assertIsNone(chunks[0][1])
        
        # Chunk 2
        self.assertEqual(chunks[1][0], "World")
        self.assertIsNone(chunks[1][1])
        
        # Chunk 3 (Usage only)
        # Chunk 3 (Usage only)
        self.assertEqual(chunks[2][0], "")
        self.assertEqual(chunks[2][2], {
            "prompt_tokens": 5,
            "completion_tokens": 2,
            "total_tokens": 7
        })

    @patch('komitto.llm.openai_client.OpenAI')
    @patch('komitto.llm.openai_client.AsyncOpenAI')
    async def test_openai_client_stream_async(self, mock_async_openai, mock_openai):
        mock_instance = MagicMock()
        mock_async_openai.return_value = mock_instance
        
        # Mock streaming chunks
        chunk1 = MagicMock()
        chunk1.choices = [MagicMock(delta=MagicMock(content="Async ", reasoning_content="Reason1"))]
        chunk1.usage = None
        
        chunk2 = MagicMock()
        chunk2.choices = [MagicMock(delta=MagicMock(content="World", reasoning_content=None))]
        chunk2.usage = None
        
        chunk3 = MagicMock()
        chunk3.choices = []
        chunk3.usage.prompt_tokens = 5
        chunk3.usage.completion_tokens = 2
        chunk3.usage.total_tokens = 7
        
        async def mock_stream():
            for c in [chunk1, chunk2, chunk3]:
                yield c
                
        import asyncio
        future = asyncio.Future()
        future.set_result(mock_stream())
        mock_instance.chat.completions.create.return_value = future

        config = {"api_key": "test_key", "model": "gpt-4"}
        client = OpenAIClient(config)
        
        chunks = []
        async for chunk in client.stream_commit_message_async("prompt"):
            chunks.append(chunk)
            
        self.assertEqual(chunks[0][0], "Async ")
        self.assertEqual(chunks[0][1], "Reason1")
        self.assertIsNone(chunks[0][2])
        
        self.assertEqual(chunks[1][0], "World")
        self.assertIsNone(chunks[1][1])
        self.assertIsNone(chunks[1][2])
        
        self.assertEqual(chunks[2][0], "")
        self.assertIsNone(chunks[2][1])
        self.assertEqual(chunks[2][2], {
            "prompt_tokens": 5,
            "completion_tokens": 2,
            "total_tokens": 7
        })

    @patch('komitto.llm.openai_client.OpenAI')
    @patch('komitto.llm.openai_client.AsyncOpenAI')
    async def test_openai_client_aclose(self, mock_async_openai, mock_openai):
        mock_instance = MagicMock()
        mock_async_openai.return_value = mock_instance
        
        # async close mock
        import asyncio
        future = asyncio.Future()
        future.set_result(None)
        mock_instance.close.return_value = future
        
        config = {"api_key": "test"}
        client = OpenAIClient(config)
        await client.aclose()
        mock_instance.close.assert_called_once()

    @patch('komitto.llm.gemini_client.genai')
    def test_gemini_client_generate(self, mock_genai):
        # Setup mock
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.text = "Commit message"
        mock_response.usage_metadata.prompt_token_count = 10
        mock_response.usage_metadata.candidates_token_count = 20
        mock_response.usage_metadata.total_token_count = 30
        
        mock_client.models.generate_content.return_value = mock_response

        # Test
        config = {"api_key": "test_key", "model": "gemini-3.5-flash"}
        client = GeminiClient(config)
        msg, usage = client.generate_commit_message("prompt")

        # Assertions
        mock_client.models.generate_content.assert_called_with(
            model="gemini-3.5-flash", contents="prompt"
        )
        self.assertEqual(msg, "Commit message")
        self.assertEqual(usage, {
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30
        })

    @patch('komitto.llm.gemini_client.genai')
    def test_gemini_client_stream(self, mock_genai):
        # Setup mock
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        
        # Mock streaming chunks
        chunk1 = MagicMock()
        chunk1.text = "Commit "
        chunk1.usage_metadata.prompt_token_count = 10
        chunk1.usage_metadata.candidates_token_count = 1
        chunk1.usage_metadata.total_token_count = 11
        
        chunk2 = MagicMock()
        chunk2.text = "message"
        chunk2.usage_metadata.prompt_token_count = 10
        chunk2.usage_metadata.candidates_token_count = 2
        chunk2.usage_metadata.total_token_count = 12
        
        mock_client.models.generate_content_stream.return_value = iter([chunk1, chunk2])

        # Test
        config = {"api_key": "test_key", "model": "gemini-3.5-flash"}
        client = GeminiClient(config)
        chunks = list(client.stream_commit_message("prompt"))
        
        # Assertions
        mock_client.models.generate_content_stream.assert_called_with(
            model="gemini-3.5-flash", contents="prompt"
        )
        self.assertEqual(chunks[0][0], "Commit ")
        self.assertEqual(chunks[1][0], "message")
        self.assertEqual(chunks[1][2]["total_tokens"], 12)

    @patch('komitto.llm.gemini_client.genai')
    async def test_gemini_client_stream_async(self, mock_genai):
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        
        chunk1 = MagicMock()
        chunk1.text = "Async "
        chunk1.usage_metadata.prompt_token_count = 10
        chunk1.usage_metadata.candidates_token_count = 1
        chunk1.usage_metadata.total_token_count = 11
        
        chunk2 = MagicMock()
        chunk2.text = "message"
        chunk2.usage_metadata.prompt_token_count = 10
        chunk2.usage_metadata.candidates_token_count = 2
        chunk2.usage_metadata.total_token_count = 12
        
        async def mock_stream():
            for c in [chunk1, chunk2]:
                yield c
                
        import asyncio
        future = asyncio.Future()
        future.set_result(mock_stream())
        mock_client.aio.models.generate_content_stream.return_value = future

        config = {"api_key": "test_key", "model": "gemini-3.5-flash"}
        client = GeminiClient(config)
        chunks = []
        async for chunk in client.stream_commit_message_async("prompt"):
            chunks.append(chunk)
            
        mock_client.aio.models.generate_content_stream.assert_called_with(
            model="gemini-3.5-flash", contents="prompt"
        )
        self.assertEqual(chunks[0][0], "Async ")
        self.assertEqual(chunks[1][0], "message")
        self.assertEqual(chunks[1][2]["total_tokens"], 12)

    @patch('komitto.llm.gemini_client.genai')
    async def test_gemini_client_aclose(self, mock_genai):
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        
        import asyncio
        future = asyncio.Future()
        future.set_result(None)
        mock_client.aio.close.return_value = future
        
        config = {"api_key": "test"}
        client = GeminiClient(config)
        await client.aclose()
        mock_client.aio.close.assert_called_once()

    @patch('komitto.llm.anthropic_client.anthropic.Anthropic')
    def test_anthropic_client_generate(self, mock_anthropic):
        # Setup mock
        mock_instance = MagicMock()
        mock_anthropic.return_value = mock_instance
        
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text="Commit message")]
        mock_message.usage.input_tokens = 10
        mock_message.usage.output_tokens = 20
        
        mock_instance.messages.create.return_value = mock_message

        # Test
        config = {"api_key": "test_key", "model": "claude-3"}
        client = AnthropicClient(config)
        msg, usage = client.generate_commit_message("prompt")

        # Assertions
        self.assertEqual(msg, "Commit message")
        self.assertEqual(usage, {
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30
        })

    def test_create_llm_client_unknown_provider(self):
        """未知のプロバイダが指定された場合に ValueError が発生することをテスト"""
        from komitto.llm.factory import create_llm_client
        with self.assertRaises(ValueError):
            create_llm_client({"provider": "unknown_provider"})

    @patch('komitto.llm.openai_client.OpenAI')
    def test_create_llm_client_openai(self, mock_openai):
        """openai プロバイダで OpenAIClient が正しく作成されることをテスト"""
        from komitto.llm.factory import create_llm_client
        client = create_llm_client({"provider": "openai", "api_key": "test"})
        self.assertEqual(client.__class__.__name__, "OpenAIClient")

    @patch('komitto.llm.gemini_client.genai')
    def test_gemini_client_missing_api_key(self, mock_genai):
        """APIキーが不足している場合に GeminiClient の初期化時に ValueError が発生することをテスト"""
        import os
        # 環境変数と config 両方から API キーを消去
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError) as ctx:
                GeminiClient({"model": "gemini-3.5-flash"})
            self.assertIn("API key is missing", str(ctx.exception))

    @patch('komitto.llm.anthropic_client.anthropic.Anthropic')
    def test_anthropic_client_missing_api_key(self, mock_anthropic):
        """APIキーが不足している場合に AnthropicClient の初期化時に ValueError が発生することをテスト"""
        import os
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError) as ctx:
                # config に api_key がない場合
                AnthropicClient({"model": "claude-3"})
            self.assertIn("API key is missing", str(ctx.exception))

    @patch('komitto.llm.openai_client.OpenAI')
    def test_openai_client_api_error_propagation(self, mock_openai):
        """API呼び出し中にエラーが発生した場合、例外がそのまま伝播することをテスト"""
        mock_instance = MagicMock()
        mock_openai.return_value = mock_instance
        # createが例外を投げるように設定
        mock_instance.chat.completions.create.side_effect = Exception("API connection timeout")

        config = {"api_key": "test_key", "model": "gpt-4"}
        client = OpenAIClient(config)
        with self.assertRaises(Exception) as ctx:
            client.generate_commit_message("prompt")
        self.assertEqual(str(ctx.exception), "API connection timeout")

    @patch('komitto.llm.anthropic_client.anthropic.Anthropic')
    @patch('komitto.llm.anthropic_client.anthropic.AsyncAnthropic')
    async def test_anthropic_client_stream_async(self, mock_async_anthropic, mock_anthropic):
        mock_instance = MagicMock()
        mock_async_anthropic.return_value = mock_instance
        
        mock_stream_ctx = AsyncMock()
        mock_instance.messages.stream.return_value = mock_stream_ctx
        
        chunk1 = "Async "
        chunk2 = "Anthropic"
        
        async def mock_text_stream():
            for c in [chunk1, chunk2]:
                yield c
                
        mock_stream_ctx.__aenter__.return_value.text_stream = mock_text_stream()
        
        mock_final_msg = MagicMock()
        mock_final_msg.usage.input_tokens = 5
        mock_final_msg.usage.output_tokens = 2
        
        mock_stream_ctx.__aenter__.return_value.get_final_message.return_value = mock_final_msg

        config = {"api_key": "test_key", "model": "claude-3"}
        client = AnthropicClient(config)
        chunks = []
        async for chunk in client.stream_commit_message_async("prompt"):
            chunks.append(chunk)

        self.assertEqual(chunks[0][0], "Async ")
        self.assertEqual(chunks[1][0], "Anthropic")
        self.assertEqual(chunks[2][0], "")
        self.assertEqual(chunks[2][2], {
            "prompt_tokens": 5,
            "completion_tokens": 2,
            "total_tokens": 7
        })

    @patch('komitto.llm.anthropic_client.anthropic.Anthropic')
    @patch('komitto.llm.anthropic_client.anthropic.AsyncAnthropic')
    async def test_anthropic_client_aclose(self, mock_async_anthropic, mock_anthropic):
        mock_instance = MagicMock()
        mock_async_anthropic.return_value = mock_instance
        
        mock_instance.close = AsyncMock()
        
        config = {"api_key": "test_key"}
        client = AnthropicClient(config)
        await client.aclose()
        mock_instance.close.assert_called_once()

if __name__ == '__main__':
    unittest.main()

