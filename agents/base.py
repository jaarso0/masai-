"""Base agent class with Groq + instructor integration."""

import asyncio
import os

import instructor
from dotenv import load_dotenv
from groq import Groq

from memory.store import save_decision

load_dotenv()


class BaseAgent:
    """Base class for all masai agents. Provides Groq API access via instructor."""

    def __init__(self) -> None:
        self.client = instructor.from_groq(
            Groq(api_key=os.environ["GROQ_API_KEY"]),
            mode=instructor.Mode.JSON,
        )
        self.model = "llama-3.3-70b-versatile"
        self.max_tokens = 8096

    async def call(self, system_prompt: str, user_prompt: str, response_model):
        """
        Call Groq API with instructor using asyncio.to_thread.
        Wraps in try/except — on failure, retry once after 10 seconds.
        On second failure, raise with a clear error message.
        """
        for attempt in range(2):
            try:
                result = await asyncio.to_thread(
                    self.client.chat.completions.create,
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    response_model=response_model,
                    max_tokens=self.max_tokens,
                )
                return result
            except Exception as e:
                if attempt == 0:
                    await asyncio.sleep(10)
                else:
                    raise RuntimeError(
                        f"[{self.__class__.__name__}] Groq call failed after 2 attempts: {e}"
                    ) from e

    def save_to_memory(self, decisions: list[str], agent_name: str) -> None:
        """Save each decision string to ChromaDB via store.save_decision."""
        for decision in decisions:
            save_decision(agent_name=agent_name, decision=decision)
