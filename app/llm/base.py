from abc import ABC, abstractmethod

class LlmClient(ABC):
    @abstractmethod
    async def generate(self, prompt: str, is_json: bool = True) -> str:
        raise NotImplementedError()