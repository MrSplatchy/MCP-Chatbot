import httpx
import asyncio

class OllamaChatClient:
    def __init__(self, model: str, host: str = "http://localhost:11434"):
        self.model = model
        self.base_url = host

    async def chat(self, messages):
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                json={"model": self.model, "messages": messages}
            )
            response.raise_for_status()
            return response.json()["message"]["content"]
