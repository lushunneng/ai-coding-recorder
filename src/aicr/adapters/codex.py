from .base import Adapter, Capabilities, UnsupportedProviderError


class CodexAdapter(Adapter):
    name = "codex"
    capabilities = Capabilities(pty=True)

    def normalize(self, raw: dict) -> dict:
        raise UnsupportedProviderError(
            "Unsupported Provider History: codex native format is not verified"
        )
