import os
from typing import Union
from google import genai
from google.genai import types
from .base import LLMClient

class GeminiClient(LLMClient):
    def __init__(self, config: dict):
        api_key = config.get("api_key") or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("Gemini API key is missing. Set it in komitto.toml or environment variable 'GEMINI_API_KEY'.")
        
        timeout = config.get("timeout", 300.0)
        self.client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=int(timeout * 1000)),
        )
        self.model_name = config.get("model", "gemini-3.5-flash")

    def _prepare_messages(self, prompt: Union[str, list]):
        if isinstance(prompt, str):
            return prompt
        
        contents = []
        for m in prompt:
            role = "model" if m["role"] == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": m["content"]}]})
        return contents

    def generate_commit_message(self, prompt: Union[str, list]):
        contents = self._prepare_messages(prompt)
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=contents
        )
        
        usage = None
        if hasattr(response, 'usage_metadata'):
             usage = {
                "prompt_tokens": response.usage_metadata.prompt_token_count,
                "completion_tokens": response.usage_metadata.candidates_token_count,
                "total_tokens": response.usage_metadata.total_token_count
            }
            
        return response.text.strip(), usage

    def stream_commit_message(self, prompt: Union[str, list]):
        contents = self._prepare_messages(prompt)
        response = self.client.models.generate_content_stream(
            model=self.model_name,
            contents=contents
        )
        
        for chunk in response:
            usage = None
            if hasattr(chunk, 'usage_metadata'):
                 usage = {
                    "prompt_tokens": chunk.usage_metadata.prompt_token_count,
                    "completion_tokens": chunk.usage_metadata.candidates_token_count,
                    "total_tokens": chunk.usage_metadata.total_token_count
                }
            yield chunk.text, None, usage

    async def stream_commit_message_async(self, prompt: Union[str, list]):
        contents = self._prepare_messages(prompt)
        response = await self.client.aio.models.generate_content_stream(
            model=self.model_name,
            contents=contents
        )
        
        async for chunk in response:
            usage = None
            if hasattr(chunk, 'usage_metadata'):
                 usage = {
                    "prompt_tokens": chunk.usage_metadata.prompt_token_count,
                    "completion_tokens": chunk.usage_metadata.candidates_token_count,
                    "total_tokens": chunk.usage_metadata.total_token_count
                }
            yield chunk.text, None, usage

    async def aclose(self) -> None:
        if hasattr(self.client, 'aio') and hasattr(self.client.aio, 'close'):
            await self.client.aio.close()
