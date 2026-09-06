from .base import Adapter, Capabilities, UnsupportedProviderError


class GeminiAdapter(Adapter):
    name = "gemini"
    capabilities = Capabilities(pty=True)

    def normalize(self, raw: dict) -> dict:
        raise UnsupportedProviderError(
            "Unsupported Provider History: gemini native format is not verified"
        )
