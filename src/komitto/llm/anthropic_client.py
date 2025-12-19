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

    def generate_commit_message(self, prompt: str):
        message = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        usage = None
        if message.usage:
            usage = {
                "prompt_tokens": message.usage.input_tokens,
                "completion_tokens": message.usage.output_tokens,
                "total_tokens": message.usage.input_tokens + message.usage.output_tokens
            }
            
        return message.content[0].text.strip(), usage

    def stream_commit_message(self, prompt: str):
        with self.client.messages.stream(
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
            model=self.model,
        ) as stream:
            for text in stream.text_stream:
                # Anthropic stream helper doesn't easily give usage per chunk yet in this simple iteration, 
                # but we can get it from stream.get_final_message() at the end.
                # For now, we yield text.
                yield text, None
            
            # After stream, try to get usage
            final_msg = stream.get_final_message()
            if final_msg.usage:
                usage = {
                    "prompt_tokens": final_msg.usage.input_tokens,
                    "completion_tokens": final_msg.usage.output_tokens,
                    "total_tokens": final_msg.usage.input_tokens + final_msg.usage.output_tokens
                }
                yield "", usage
