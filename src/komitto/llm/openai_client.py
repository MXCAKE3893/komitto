import os
from openai import OpenAI
from .base import LLMClient

class OpenAIClient(LLMClient):
    def __init__(self, config: dict):
        api_key = config.get("api_key") or os.environ.get("OPENAI_API_KEY")
        base_url = config.get("base_url")
        
        if not api_key and not base_url: 
            # Local endpoints like Ollama might not strictly require an API key, 
            # but standard OpenAI does. We'll warn or let the SDK handle the error if missing.
            pass

        self.client = OpenAI(
            api_key=api_key or "dummy", # Some local servers need a dummy key
            base_url=base_url
        )
        self.model = config.get("model", "gpt-3.5-turbo")

    def generate_commit_message(self, prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content.strip()
