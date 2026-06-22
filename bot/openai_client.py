from collections.abc import AsyncGenerator

import litellm

from .prompts import SYSTEM_PROMPT

_MESSAGES = lambda user_text: [  # noqa: E731
    {"role": "system", "content": SYSTEM_PROMPT},
    {"role": "user", "content": user_text},
]


async def complete(model: str, api_key: str, user_text: str) -> str:
    resp = await litellm.acompletion(
        model=model,
        api_key=api_key,
        timeout=120,
        messages=_MESSAGES(user_text),
    )
    return resp.choices[0].message.content or ""


async def complete_stream(model: str, api_key: str, user_text: str) -> AsyncGenerator[str, None]:
    resp = await litellm.acompletion(
        model=model,
        api_key=api_key,
        timeout=120,
        stream=True,
        messages=_MESSAGES(user_text),
    )
    async for chunk in resp:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta
