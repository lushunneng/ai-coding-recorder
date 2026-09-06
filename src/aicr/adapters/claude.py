from .base import Adapter, Capabilities, UnsupportedProviderError


class ClaudeAdapter(Adapter):
    name = "claude"
    capabilities = Capabilities(pty=True)

    def normalize(self, raw: dict) -> dict:
        raise UnsupportedProviderError(
            "Unsupported Provider History: claude native format is not verified"
        )
