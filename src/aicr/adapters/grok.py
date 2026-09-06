from .base import Adapter, Capabilities, UnsupportedProviderError


class GrokAdapter(Adapter):
    name = "grok"
    capabilities = Capabilities(pty=True)

    def normalize(self, raw: dict) -> dict:
        raise UnsupportedProviderError(
            "Unsupported Provider History: grok native format is not verified"
        )
