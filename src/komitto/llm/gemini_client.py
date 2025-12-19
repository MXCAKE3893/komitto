import os
import google.generativeai as genai
from .base import LLMClient

class GeminiClient(LLMClient):
    def __init__(self, config: dict):
        api_key = config.get("api_key") or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("Gemini API key is missing. Set it in komitto.toml or environment variable 'GEMINI_API_KEY'.")
        
        genai.configure(api_key=api_key)
        self.model_name = config.get("model", "gemini-pro")

    def generate_commit_message(self, prompt: str):
        model = genai.GenerativeModel(self.model_name)
        response = model.generate_content(prompt)
        
        usage = None
        if hasattr(response, 'usage_metadata'):
             usage = {
                "prompt_tokens": response.usage_metadata.prompt_token_count,
                "completion_tokens": response.usage_metadata.candidates_token_count,
                "total_tokens": response.usage_metadata.total_token_count
            }
            
        return response.text.strip(), usage

    def stream_commit_message(self, prompt: str):
        model = genai.GenerativeModel(self.model_name)
        response = model.generate_content(prompt, stream=True)
        
        for chunk in response:
            usage = None
            if hasattr(chunk, 'usage_metadata'):
                 usage = {
                    "prompt_tokens": chunk.usage_metadata.prompt_token_count,
                    "completion_tokens": chunk.usage_metadata.candidates_token_count,
                    "total_tokens": chunk.usage_metadata.total_token_count
                }
            yield chunk.text, usage
