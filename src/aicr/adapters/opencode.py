from .base import Adapter, Capabilities, UnsupportedProviderError


class OpencodeAdapter(Adapter):
    name = "opencode"
    capabilities = Capabilities(pty=True)

    def normalize(self, raw: dict) -> dict:
        raise UnsupportedProviderError(
            "Unsupported Provider History: opencode native format is not verified"
        )
