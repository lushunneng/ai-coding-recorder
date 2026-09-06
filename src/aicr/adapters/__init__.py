from .base import Adapter as Adapter
from .base import UnsupportedProviderError as UnsupportedProviderError
from .generic import GenericAdapter

ADAPTERS = {"generic": GenericAdapter}


def get_adapter(name: str):
    return ADAPTERS.get(name, GenericAdapter)
