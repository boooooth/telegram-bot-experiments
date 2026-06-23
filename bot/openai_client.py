import logging
from collections.abc import AsyncGenerator

import litellm

from .prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

_MESSAGES = lambda user_text: [  # noqa: E731
    {"role": "system", "content": SYSTEM_PROMPT},
    {"role": "user", "content": user_text},
]


def _image_messages(image_b64: str, caption: str) -> list:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": caption},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
                },
            ],
        },
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


async def complete_stream_image(
    model: str, api_key: str, image_b64: str, caption: str
) -> AsyncGenerator[str, None]:
    logger.info("vision request: model=%s image_b64_len=%d caption=%r", model, len(image_b64), caption)
    resp = await litellm.acompletion(
        model=model,
        api_key=api_key,
        timeout=120,
        stream=True,
        messages=_image_messages(image_b64, caption),
    )
    async for chunk in resp:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta
