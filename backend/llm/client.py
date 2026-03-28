"""Async OpenAI-compatible LLM client with concurrency limits and JSON parsing."""

import asyncio
import json
import logging
import re
from typing import Optional

from openai import AsyncOpenAI

from config import settings

logger = logging.getLogger("agentica.llm")


class LLMClient:
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.llm_api_key or "dummy",
            base_url=settings.llm_base_url,
        )
        self.model = settings.llm_model_name
        self.semaphore = asyncio.Semaphore(settings.llm_max_concurrent_requests)
        self.total_tokens_used = 0
        self.total_calls = 0

    # Global rules appended to every system prompt
    GLOBAL_RULES = (
        "\nIMPORTANT RULES:"
        "\n- Never use em dashes in your responses. Use commas, periods, or semicolons instead."
        "\n- You are in a primitive frontier settlement with NO modern technology, NO electricity, NO phones, NO internet, NO computers, NO corporate tools."
        "\n- Think and speak as someone starting a new life in the wilderness. Reference only things in your immediate physical world: nature, food, shelter, other settlers, weather, terrain, hand tools."
        "\n- Keep responses short and natural. 1-2 sentences max."
    )

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.8,
        max_tokens: int = 500,
    ) -> Optional[str]:
        """Generate a completion. Returns raw text or None on failure."""
        async with self.semaphore:
            try:
                response = await asyncio.wait_for(
                    self.client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {"role": "system", "content": system_prompt + self.GLOBAL_RULES},
                            {"role": "user", "content": user_prompt},
                        ],
                        temperature=temperature,
                        max_completion_tokens=max_tokens,
                    ),
                    timeout=settings.llm_call_timeout_seconds,
                )
                self.total_calls += 1
                if response.usage:
                    self.total_tokens_used += response.usage.total_tokens

                content = response.choices[0].message.content
                return content

            except asyncio.TimeoutError:
                logger.warning("LLM call timed out")
                return None
            except Exception as e:
                logger.error(f"LLM call failed: {e}")
                return None

    async def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        default: dict | None = None,
        temperature: float = 0.8,
        max_tokens: int = 500,
    ) -> dict:
        """Generate and parse JSON response. Returns default on failure."""
        raw = await self.generate(system_prompt, user_prompt, temperature, max_tokens)
        if raw is None:
            return default or {}

        parsed = parse_json_response(raw)
        if parsed is None:
            logger.warning(f"Failed to parse JSON from LLM response: {raw[:200]}")
            return default or {}
        return parsed


def parse_json_response(text: str) -> Optional[dict]:
    """Try to extract JSON from LLM response."""
    # Direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Extract from markdown code block
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Try to find a JSON object in the text
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    # Fix common issues: trailing commas
    cleaned = re.sub(r",\s*([}\]])", r"\1", text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    return None


# Singleton
llm_client = LLMClient()
