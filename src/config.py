"""Configuration and credential management.

Loads settings from environment variables (.env file supported).
Never hardcodes secrets — follows security.md requirements.
"""

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass
class AzureSpeechConfig:
    subscription_key: str = field(default_factory=lambda: os.environ.get("AZURE_SPEECH_KEY", ""))
    region: str = field(default_factory=lambda: os.environ.get("AZURE_SPEECH_REGION", "japaneast"))
    language: str = field(default_factory=lambda: os.environ.get("SPEECH_LANGUAGE", "ja-JP"))


@dataclass
class AzureOpenAIConfig:
    api_key: str = field(default_factory=lambda: os.environ.get("AZURE_OPENAI_KEY", ""))
    endpoint: str = field(default_factory=lambda: os.environ.get("AZURE_OPENAI_ENDPOINT", ""))
    deployment: str = field(default_factory=lambda: os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o"))
    api_version: str = field(default_factory=lambda: os.environ.get("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"))
    timeout_sec: float = field(default_factory=lambda: float(os.environ.get("AZURE_OPENAI_TIMEOUT_SEC", "1.8")))
    max_output_tokens: int = field(default_factory=lambda: int(os.environ.get("AZURE_OPENAI_MAX_OUTPUT_TOKENS", "96")))
    temperature: float = field(default_factory=lambda: float(os.environ.get("AZURE_OPENAI_TEMPERATURE", "0.0")))
    min_chars_for_api: int = field(default_factory=lambda: int(os.environ.get("REFINE_MIN_CHARS_FOR_API", "8")))


@dataclass
class AppConfig:
    hotkey: str = field(default_factory=lambda: os.environ.get("HOTKEY", "ctrl+shift+space"))
    enable_refinement: bool = field(default_factory=lambda: os.environ.get("ENABLE_REFINEMENT", "false").lower() == "true")
    output_post_hotkey_delay_sec: float = field(
        default_factory=lambda: float(os.environ.get("OUTPUT_POST_HOTKEY_DELAY_SEC", "0.5"))
    )
    speech: AzureSpeechConfig = field(default_factory=AzureSpeechConfig)
    openai: AzureOpenAIConfig = field(default_factory=AzureOpenAIConfig)

    def validate(self) -> list[str]:
        errors = []
        if not self.speech.subscription_key:
            errors.append("AZURE_SPEECH_KEY is not set")
        if not self.speech.region:
            errors.append("AZURE_SPEECH_REGION is not set")
        if self.enable_refinement:
            if not self.openai.api_key:
                errors.append("AZURE_OPENAI_KEY is not set (required when refinement is enabled)")
            if not self.openai.endpoint:
                errors.append("AZURE_OPENAI_ENDPOINT is not set (required when refinement is enabled)")
        return errors
