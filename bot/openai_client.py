import litellm

from .prompts import SYSTEM_PROMPT


async def complete(model: str, api_key: str, user_text: str) -> str:
    resp = await litellm.acompletion(
        model=model,
        api_key=api_key,
        timeout=30,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
    )
    return resp.choices[0].message.content or ""
