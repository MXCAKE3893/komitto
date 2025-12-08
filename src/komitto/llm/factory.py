from .openai_client import OpenAIClient
from .gemini_client import GeminiClient
from .anthropic_client import AnthropicClient

def create_llm_client(config: dict):
    provider = config.get("provider", "openai").lower()
    
    if provider == "openai":
        return OpenAIClient(config)
    elif provider == "gemini":
        return GeminiClient(config)
    elif provider == "anthropic":
        return AnthropicClient(config)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")
