"""
gas.py - Gas cost oracle.

Computes the USD cost of sending a single ERC-20 transfer:

  gas_cost_usd = gas_units * gas_price_native * native_price_usd

`gas_price_native` is in wei (legacy). `native_price_usd` is the USD
value of one unit of native gas currency (e.g. PROS on Pharos
mainnet). The native price is supplied by the caller; the engine
does not maintain a price oracle for the native token (use an
external feed for production, or pass `--native-price-usd 0` to
fall back to gas-token-only reporting).
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from rpc import RpcClient, RpcError


# Default gas units for a plain ERC-20 transfer. Real-world 21k is
# the native send; ERC-20 transfer typically runs 50-80k on modern
# chains. We default to 65000.
DEFAULT_GAS_UNITS_ERC20 = 65_000


@dataclass
class GasQuote:
    gas_price_wei: int
    gas_units: int
    native_price_usd: float      # USD per 1 native token (e.g. per PROS)

    @property
    def gas_cost_native(self) -> float:
        return (self.gas_price_wei * self.gas_units) / 1e18

    @property
    def gas_cost_usd(self) -> float:
        return self.gas_cost_native * self.native_price_usd


def quote(rpc: RpcClient, gas_units: int = DEFAULT_GAS_UNITS_ERC20,
          native_price_usd: float = 0.0) -> GasQuote:
    """Fetch the current gas price and assemble a quote."""
    try:
        gp = rpc.gas_price()
    except RpcError as e:
        raise RpcError(f"gas oracle failed: {e}")
    return GasQuote(
        gas_price_wei=gp,
        gas_units=gas_units,
        native_price_usd=native_price_usd,
    )
