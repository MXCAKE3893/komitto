import unittest
from unittest.mock import MagicMock, patch
from komitto.llm.openai_client import OpenAIClient
from komitto.llm.gemini_client import GeminiClient
from komitto.llm.anthropic_client import AnthropicClient

class TestLLMClients(unittest.TestCase):

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
        chunk1.choices = [MagicMock(delta=MagicMock(content="Hello "))]
        chunk1.usage = None
        
        chunk2 = MagicMock()
        chunk2.choices = [MagicMock(delta=MagicMock(content="World"))]
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
        self.assertEqual(chunks[2][0], "")
        self.assertEqual(chunks[2][1], {
            "prompt_tokens": 5,
            "completion_tokens": 2,
            "total_tokens": 7
        })

    @patch('komitto.llm.gemini_client.genai')
    def test_gemini_client_generate(self, mock_genai):
        # Setup mock
        mock_model = MagicMock()
        mock_genai.GenerativeModel.return_value = mock_model
        
        mock_response = MagicMock()
        mock_response.text = "Commit message"
        mock_response.usage_metadata.prompt_token_count = 10
        mock_response.usage_metadata.candidates_token_count = 20
        mock_response.usage_metadata.total_token_count = 30
        
        mock_model.generate_content.return_value = mock_response

        # Test
        config = {"api_key": "test_key", "model": "gemini-pro"}
        client = GeminiClient(config)
        msg, usage = client.generate_commit_message("prompt")

        # Assertions
        self.assertEqual(msg, "Commit message")
        self.assertEqual(usage, {
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30
        })

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

if __name__ == '__main__':
    unittest.main()
