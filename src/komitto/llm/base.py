from abc import ABC, abstractmethod

class LLMClient(ABC):
    @abstractmethod
    def generate_commit_message(self, prompt: str) -> str:
        """
        Generate a commit message based on the provided prompt.
        """
        pass
