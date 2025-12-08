import os
import anthropic
from .base import LLMClient

class AnthropicClient(LLMClient):
    def __init__(self, config: dict):
        api_key = config.get("api_key") or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("Anthropic API key is missing. Set it in komitto.toml or environment variable 'ANTHROPIC_API_KEY'.")
        
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = config.get("model", "claude-3-opus-20240229")

    def generate_commit_message(self, prompt: str) -> str:
        message = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        return message.content[0].text.strip()
