from abc import ABC, abstractmethod

class LlmClient(ABC):
    @abstractmethod
    async def generate(self, prompt: str) -> str:
        raise NotImplementedError()