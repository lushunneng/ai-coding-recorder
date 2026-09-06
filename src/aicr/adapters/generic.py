from .base import Adapter, Capabilities


class GenericAdapter(Adapter):
    name = "generic"
    capabilities = Capabilities(pty=True, import_mode=True)

    def normalize(self, raw: dict) -> dict:
        return {
            **raw,
            "schema_version": 1,
            "provider": "generic",
            "capture_mode": "pty",
            "stream": "merged",
            "confidence": "observed",
        }
