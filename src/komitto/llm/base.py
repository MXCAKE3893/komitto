from abc import ABC, abstractmethod
from typing import Generator, Tuple, Optional, Dict, Any

class LLMClient(ABC):
    @abstractmethod
    def generate_commit_message(self, prompt: str) -> Tuple[str, Optional[Dict[str, int]]]:
        """
        Generate a commit message based on the provided prompt.
        Returns: (message, usage_metadata)
        """
        pass

    def stream_commit_message(self, prompt: str) -> Generator[Tuple[str, Optional[Dict[str, Any]]], None, None]:
        """
        Yields (chunk_text, metadata) tuples.
        Default implementation wraps generate_commit_message for non-streaming clients.
        """
        msg, usage = self.generate_commit_message(prompt)
        yield msg, usage