from .base import Adapter as Adapter
from .base import UnsupportedProviderError as UnsupportedProviderError
from .claude import ClaudeAdapter
from .codex import CodexAdapter
from .gemini import GeminiAdapter
from .generic import GenericAdapter
from .grok import GrokAdapter
from .opencode import OpencodeAdapter

ADAPTERS = {
    "generic": GenericAdapter,
    "claude": ClaudeAdapter,
    "codex": CodexAdapter,
    "gemini": GeminiAdapter,
    "grok": GrokAdapter,
    "opencode": OpencodeAdapter,
}


def get_adapter(name: str):
    return ADAPTERS.get(name, GenericAdapter)
