import os
from google import genai
from .base import LLMClient

class GeminiClient(LLMClient):
    def __init__(self, config: dict):
        api_key = config.get("api_key") or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("Gemini API key is missing. Set it in komitto.toml or environment variable 'GEMINI_API_KEY'.")
        
        self.client = genai.Client(api_key=api_key)
        self.model_name = config.get("model", "gemini-pro")

    def generate_commit_message(self, prompt: str):
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt
        )
        
        usage = None
        if hasattr(response, 'usage_metadata'):
             usage = {
                "prompt_tokens": response.usage_metadata.prompt_token_count,
                "completion_tokens": response.usage_metadata.candidates_token_count,
                "total_tokens": response.usage_metadata.total_token_count
            }
            
        return response.text.strip(), usage

    def stream_commit_message(self, prompt: str):
        response = self.client.models.generate_content_stream(
            model=self.model_name,
            contents=prompt
        )
        
        for chunk in response:
            usage = None
            if hasattr(chunk, 'usage_metadata'):
                 usage = {
                    "prompt_tokens": chunk.usage_metadata.prompt_token_count,
                    "completion_tokens": chunk.usage_metadata.candidates_token_count,
                    "total_tokens": chunk.usage_metadata.total_token_count
                }
            yield chunk.text, usage
