from dataclasses import dataclass


class UnsupportedProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class Capabilities:
    pty: bool = False
    native: bool = False
    import_mode: bool = False


class Adapter:
    name = "unknown"
    capabilities = Capabilities()

    def normalize(self, raw: dict) -> dict:
        raise UnsupportedProviderError(f"Unsupported Provider: {self.name}")
