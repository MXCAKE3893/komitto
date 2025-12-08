def create_llm_client(config: dict):
    provider = config.get("provider", "openai").lower()
    
    if provider == "openai":
        from .openai_client import OpenAIClient
        return OpenAIClient(config)
    elif provider == "gemini":
        from .gemini_client import GeminiClient
        return GeminiClient(config)
    elif provider == "anthropic":
        from .anthropic_client import AnthropicClient
        return AnthropicClient(config)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")
