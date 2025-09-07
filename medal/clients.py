import asyncio
from typing import Optional

from openai import AsyncOpenAI


def make_openai_async_client(api_key: Optional[str] = None) -> AsyncOpenAI:
    return AsyncOpenAI(api_key=api_key)


async def bounded_json_chat_completion(
    client: AsyncOpenAI,
    model: str,
    prompt: str,
    semaphore: asyncio.Semaphore,
    temperature: Optional[float] = 0.2,
    reasoning_effort: Optional[str] = None,
) -> str:
    async with semaphore:
        # Use Responses API for GPT-5 family
        if model.startswith("gpt-5"):
            # Try Responses API with reasoning; fall back if unsupported
            try:
                resp = await client.responses.create(
                    model=model,
                    input=prompt,
                    reasoning={"effort": reasoning_effort} if reasoning_effort else None,
                )
            except TypeError:
                # Retry without reasoning field for older SDKs
                resp = await client.responses.create(
                    model=model,
                    input=prompt,
                )
            # Try convenient property first
            text = getattr(resp, "output_text", None)
            if text:
                return text
            # Fallback: extract from output/content lists
            try:
                parts = []
                output = getattr(resp, "output", None) or getattr(resp, "content", None) or []
                for item in output or []:
                    content_list = getattr(item, "content", None) or []
                    for c in content_list:
                        t = getattr(c, "text", None)
                        if t:
                            parts.append(getattr(t, "value", None) or str(t))
                if parts:
                    return "\n".join(parts)
            except Exception:
                pass
            # As a last resort, return stringified object
            return str(resp)

        # Otherwise, use Chat Completions API
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
        }
        if temperature is not None:
            payload["temperature"] = temperature
        completion = await client.chat.completions.create(**payload)
        return completion.choices[0].message.content



