# Shared text model client routed by role.
# Descriptor uses GPT on Replicate specialist uses Kimi and judge uses DeepSeek.
# Roles stay on separate models. API keys are used due to GPU hardware limits.
from __future__ import annotations
import logging
import os
from enum import Enum
from src.config import Settings

logger = logging.getLogger(__name__)


class TextRole(str, Enum):
    DESCRIPTOR = "descriptor"
    SPECIALIST = "specialist"
    JUDGE = "judge"


# Resolves the Replicate API token from settings or environment.
def _replicate_token(settings: Settings) -> str:
    token = (
        settings.musicgen_api_key.strip()
        or os.getenv("REPLICATE_API_TOKEN", "").strip()
        or os.getenv("MUSICGEN_API_KEY", "").strip()
    )
    token = token.strip().strip('"')
    if not token:
        raise RuntimeError(
            "Replicate token required — set MUSICGEN_API_KEY or REPLICATE_API_TOKEN "
            "in backend/.env"
        )
    return token


def _output_text(output: object) -> str:
    if isinstance(output, list):
        return "".join(str(x) for x in output)
    return str(output) if output is not None else ""


# Chooses Kimi temperature based on model family and thinking settings.
def _kimi_temperature(model: str, requested: float, *, thinking_disabled: bool = False) -> float:
    name = (model or "").strip().lower()
    if thinking_disabled and (
        name.startswith("kimi-k2.5") or name.startswith("kimi-k2.6")
    ):
        return 0.6
    if name.startswith("kimi-k2") or name.startswith("kimi-k3"):
        return 1.0
    return requested


# Only newer Kimi models support disabling thinking.
# Older Moonshot models are deprecated.
def _kimi_supports_disable_thinking(model: str) -> bool:
    name = (model or "").strip().lower()
    return name.startswith("kimi-k2.5") or name.startswith("kimi-k2.6")


# Normalizes the Kimi base URL to the preferred host.
def _normalize_kimi_base_url(url: str) -> str:
    raw = (url or "").strip().strip('"') or "https://api.moonshot.ai/v1"
    lowered = raw.lower()
    if "moonshot.cn" in lowered:
        logger.warning(
            "KIMI_BASE_URL pointed at moonshot.cn (%s); rewriting to api.moonshot.ai/v1",
            raw,
        )
        return "https://api.moonshot.ai/v1"
    return raw.rstrip("/")

# Calls Kimi for specialist generation.
def _chat_kimi(
    settings: Settings,
    *,
    system: str,
    user: str,
    temperature: float,
    max_tokens: int,
) -> str:
    from openai import OpenAI

    if not settings.kimi_api_key.strip():
        raise RuntimeError(
            "KIMI_API_KEY is not configured. Set it in backend/.env for specialist LLMs."
        )
    model = settings.kimi_text_model
    base_url = _normalize_kimi_base_url(settings.kimi_base_url)
    disable_thinking = _kimi_supports_disable_thinking(model)
    temp = _kimi_temperature(model, temperature, thinking_disabled=disable_thinking)
    if temp != temperature:
        logger.info(
            "Kimi model %s temperature adjusted %.2f → %.2f (thinking_disabled=%s)",
            model,
            temperature,
            temp,
            disable_thinking,
        )
    client = OpenAI(
        api_key=settings.kimi_api_key.strip().strip('"'),
        base_url=base_url,
    )
    # Build request options and optionally disable thinking.
    create_kwargs: dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temp,
        "max_tokens": max_tokens,
    }
    if disable_thinking:
        create_kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
        logger.info(
            "Kimi %s @ %s: thinking disabled, temperature=%.2f",
            model,
            base_url,
            temp,
        )

    response = client.chat.completions.create(**create_kwargs)
    message = response.choices[0].message
    content = message.content or ""
    if content.strip():
        return content

    reasoning = getattr(message, "reasoning_content", None) or ""
    finish = getattr(response.choices[0], "finish_reason", None)
    if reasoning:
        logger.warning(
            "Kimi returned empty content (finish_reason=%s); reasoning_content length=%d",
            finish,
            len(reasoning),
        )
        raise RuntimeError(
            "Kimi returned empty content (thinking used the token budget). "
            "Retry, raise max_tokens, or keep thinking disabled for specialists."
        )
    return ""


# Calls GPT on Replicate for brand descriptor generation.
def _chat_gpt4o_replicate(
    settings: Settings,
    *,
    system: str,
    user: str,
    temperature: float,
    max_tokens: int,
) -> str:
    import replicate

    client = replicate.Client(api_token=_replicate_token(settings))
    model = settings.gpt4o_replicate_model.strip().strip('"')
    logger.info("Calling GPT-4o (Replicate): %s", model)
    output = client.run(
        model,
        input={
            "system_prompt": system,
            "prompt": user,
            "temperature": temperature,
            "max_completion_tokens": max_tokens,
        },
    )
    return _output_text(output)


# Calls DeepSeek on Replicate for congruence judging.
def _chat_deepseek_replicate(
    settings: Settings,
    *,
    system: str,
    user: str,
    temperature: float,
    max_tokens: int,
) -> str:
    import replicate

    client = replicate.Client(api_token=_replicate_token(settings))
    model = settings.deepseek_replicate_model.strip().strip('"')
    logger.info("Calling DeepSeek judge (Replicate): %s", model)
    prompt = f"{system}\n\n{user}"
    output = client.run(
        model,
        input={
            "prompt": prompt,
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
    )
    return _output_text(output)


# Dispatches a chat call to the provider configured for that role.
def chat_completion(
    role: TextRole | str,
    *,
    system: str,
    user: str,
    temperature: float = 0.3,
    max_tokens: int = 1024,
    settings: Settings | None = None,
) -> str:
    settings = settings or Settings()
    role_key = TextRole(role) if not isinstance(role, TextRole) else role

    if role_key is TextRole.DESCRIPTOR:
        return _chat_gpt4o_replicate(
            settings,
            system=system,
            user=user,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    if role_key is TextRole.SPECIALIST:
        return _chat_kimi(
            settings,
            system=system,
            user=user,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    if role_key is TextRole.JUDGE:
        return _chat_deepseek_replicate(
            settings,
            system=system,
            user=user,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    raise RuntimeError(f"Unknown text role: {role_key!r}")


# Fails early if credentials for the role are missing.
def require_role_credentials(role: TextRole | str, settings: Settings | None = None) -> None:
    settings = settings or Settings()
    role_key = TextRole(role) if not isinstance(role, TextRole) else role
    if role_key is TextRole.SPECIALIST:
        if not settings.kimi_api_key.strip():
            raise RuntimeError(
                "KIMI_API_KEY is not configured. Set it in backend/.env for "
                "fragrance/music specialist generation."
            )
        return
    # Descriptor and judge both need a Replicate token.
    _replicate_token(settings)
