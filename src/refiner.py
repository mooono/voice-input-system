"""Text refinement module using Azure OpenAI."""

import logging
from time import perf_counter
from typing import Literal

from openai import APIStatusError, AzureOpenAI, OpenAI

from .config import AzureOpenAIConfig

logger = logging.getLogger(__name__)

_CLIENT_CACHE: dict[tuple[str, str, str], AzureOpenAI | OpenAI] = {}

SYSTEM_PROMPT = (
    "音声テキストを整形し出力。"
    "「ええと」「あの」「えー」「まあ」「なんか」「うーん」等のフィラーを必ず削除。"
    "誤字修正、句読点補正。意味を変えず整形後テキストのみ返す。"
)


def _is_foundry_endpoint(endpoint: str) -> bool:
    """Detect Azure AI Foundry project endpoints."""
    endpoint_l = endpoint.lower()
    return "/api/projects/" in endpoint_l or ".services.ai.azure.com" in endpoint_l


def _is_openai_compatible_endpoint(endpoint: str) -> bool:
    """Detect OpenAI-compatible endpoint style (e.g. .../openai/v1)."""
    endpoint_l = endpoint.lower().rstrip("/")
    return endpoint_l.endswith("/openai/v1") or endpoint_l.endswith("/v1")


def _endpoint_mode(endpoint: str) -> Literal["foundry", "openai_compatible", "azure_legacy"]:
    if _is_foundry_endpoint(endpoint):
        return "foundry"
    if _is_openai_compatible_endpoint(endpoint):
        return "openai_compatible"
    return "azure_legacy"


def _build_base_url(endpoint: str) -> str:
    """Normalise endpoint to an OpenAI-compatible base URL (/openai/v1 or /v1)."""
    url = endpoint.rstrip("/")
    idx = url.find("/v1")
    if idx != -1:
        url = url[: idx + 3]
    elif not url.endswith("/openai/v1"):
        url = url + "/openai/v1"
    return url


def _create_client(cfg: AzureOpenAIConfig) -> AzureOpenAI | OpenAI:
    cache_key = (cfg.endpoint, cfg.api_key, cfg.api_version)
    cached = _CLIENT_CACHE.get(cache_key)
    if cached is not None:
        return cached

    mode = _endpoint_mode(cfg.endpoint)
    if mode in ("foundry", "openai_compatible"):
        base_url = _build_base_url(cfg.endpoint)
        logger.info("Using OpenAI client (%s endpoint): %s", mode, base_url)
        client = OpenAI(api_key=cfg.api_key, base_url=base_url, timeout=cfg.timeout_sec)
    else:
        logger.info("Using AzureOpenAI client (legacy endpoint): %s", cfg.endpoint)
        client = AzureOpenAI(
            api_key=cfg.api_key,
            api_version=cfg.api_version,
            azure_endpoint=cfg.endpoint,
            timeout=cfg.timeout_sec,
        )

    _CLIENT_CACHE[cache_key] = client
    return client


def warmup(cfg: AzureOpenAIConfig) -> None:
    """Pre-create the HTTP client so the first real call skips DNS/TLS setup."""
    try:
        _create_client(cfg)
        logger.info("OpenAI client warmed up")
    except Exception:
        logger.debug("Client warmup failed (will retry on first call)")


def _collect_stream(stream) -> str:
    """Collect a streaming chat completion into a single string."""
    chunks: list[str] = []
    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            chunks.append(chunk.choices[0].delta.content)
    return "".join(chunks)


def refine_text(text: str, cfg: AzureOpenAIConfig) -> str:
    """Send recognized text to Azure OpenAI for refinement.

    Uses streaming to eliminate server-side response buffering delay.
    """
    text = text.strip()
    if not text:
        return text

    # Fast path: very short text gains little from cloud refinement.
    if len(text) < cfg.min_chars_for_api:
        return text

    client = _create_client(cfg)
    mode = _endpoint_mode(cfg.endpoint)
    t0 = perf_counter()

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": text},
    ]

    try:
        if mode == "foundry":
            # Foundry responses API — use streaming
            stream = client.responses.create(
                model=cfg.deployment,
                instructions=SYSTEM_PROMPT,
                input=text,
                temperature=cfg.temperature,
                max_output_tokens=cfg.max_output_tokens,
                stream=True,
            )
            chunks: list[str] = []
            for event in stream:
                if hasattr(event, "delta") and isinstance(event.delta, str):
                    chunks.append(event.delta)
            refined = "".join(chunks)
        else:
            # chat.completions (azure_legacy / openai_compatible) — streaming
            stream = client.chat.completions.create(
                model=cfg.deployment,
                messages=messages,
                temperature=cfg.temperature,
                max_tokens=cfg.max_output_tokens,
                stream=True,
            )
            refined = _collect_stream(stream)

        if refined:
            elapsed_ms = (perf_counter() - t0) * 1000
            logger.info("Text refined in %.0f ms: %d → %d chars", elapsed_ms, len(text), len(refined))
            return refined.strip()
        return text
    except APIStatusError as e:
        if mode == "foundry" and getattr(e, "status_code", None) == 400:
            logger.error(
                "Foundry endpoint returned 400 UserError. Check AZURE_OPENAI_DEPLOYMENT is the project's deployed model name, "
                "and AZURE_OPENAI_KEY is the project/resource key for this endpoint."
            )
        logger.error(
            "Text refinement failed: status=%s endpoint=%s body=%s",
            getattr(e, "status_code", "unknown"),
            cfg.endpoint,
            getattr(e, "response", None),
        )
        logger.exception("Text refinement failed — returning original text")
        return text
    except Exception:
        logger.exception("Text refinement failed — returning original text")
        return text
