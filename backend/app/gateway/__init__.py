"""The model gateway: the one package through which every model call passes.

`Gateway` joins these exports in a later work item (docs/design/gateway-lld.md).
"""

from app.gateway.types import GatewayRequest, GatewayResponse

__all__ = ["GatewayRequest", "GatewayResponse"]
