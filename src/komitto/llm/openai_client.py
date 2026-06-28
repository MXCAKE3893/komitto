import os
from typing import Union
from openai import AsyncOpenAI, OpenAI
from .base import LLMClient

class OpenAIClient(LLMClient):
    def __init__(self, config: dict):
        api_key = config.get("api_key") or os.environ.get("OPENAI_API_KEY")
        base_url = config.get("base_url")
        
        if not api_key and not base_url: 
            # Local endpoints like Ollama might not strictly require an API key, 
            # but standard OpenAI does. We'll warn or let the SDK handle the error if missing.
            pass

        common_kwargs = {
            "api_key": api_key or "dummy",
            "base_url": base_url,
            "timeout": config.get("timeout", 300.0),
            "max_retries": config.get("max_retries", 2),
        }

        self.client = OpenAI(**common_kwargs)
        self.async_client = AsyncOpenAI(**common_kwargs)
        self.model = config.get("model", "gpt-5.4-mini")

    def _prepare_messages(self, prompt: Union[str, list]):
        if isinstance(prompt, str):
            return [{"role": "user", "content": prompt}]
        return prompt

    def generate_commit_message(self, prompt: Union[str, list]):
        messages = self._prepare_messages(prompt)
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages
        )
        content = response.choices[0].message.content.strip()
        
        usage = None
        if response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
            
        return content, usage

    def stream_commit_message(self, prompt: Union[str, list]):
        messages = self._prepare_messages(prompt)
        
        try:
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True,
                stream_options={"include_usage": True}
            )
        except TypeError:
            # Fallback for older SDKs or backends that don't support stream_options
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True
            )

        for chunk in stream:
            content = chunk.choices[0].delta.content if chunk.choices else None
            reasoning_content = getattr(chunk.choices[0].delta, 'reasoning_content', None) if chunk.choices else None
            
            usage = None
            if hasattr(chunk, "usage") and chunk.usage:
                usage = {
                    "prompt_tokens": chunk.usage.prompt_tokens,
                    "completion_tokens": chunk.usage.completion_tokens,
                    "total_tokens": chunk.usage.total_tokens
                }
            
            if content or reasoning_content:
                yield content, reasoning_content, usage
            elif usage:
                yield "", None, usage

    async def stream_commit_message_async(self, prompt: Union[str, list]):
        messages = self._prepare_messages(prompt)
        
        try:
            stream = await self.async_client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True,
                stream_options={"include_usage": True}
            )
        except TypeError:
            # Fallback for older SDKs or backends that don't support stream_options
            stream = await self.async_client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True
            )

        async for chunk in stream:
            content = chunk.choices[0].delta.content if chunk.choices else None
            reasoning_content = getattr(chunk.choices[0].delta, 'reasoning_content', None) if chunk.choices else None
            
            usage = None
            if hasattr(chunk, "usage") and chunk.usage:
                usage = {
                    "prompt_tokens": chunk.usage.prompt_tokens,
                    "completion_tokens": chunk.usage.completion_tokens,
                    "total_tokens": chunk.usage.total_tokens
                }
            
            if content or reasoning_content:
                yield content, reasoning_content, usage
            elif usage:
                yield "", None, usage

    async def aclose(self) -> None:
        await self.async_client.close()
