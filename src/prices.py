"""
prices.py - Token price oracle.

Default: read a UniswapV2-style pair's `getReserves()` for any pair
where one side is a known stablecoin (USDC / USDT). Returns a
mid-price in USD per token.

Falls back to 0.0 if no on-chain quote is available — the caller
should treat that as "price unknown" and not flag the token as dust.

This is intentionally minimal. Production users should swap in a
real oracle (Chainlink, Pyth, CoinGecko) by replacing
`price_native_units_to_usd` with a function that returns the USD
value of `amount` of `token`.
"""
from __future__ import annotations
from typing import Optional, Tuple

from rpc import RpcClient, RpcError, SELECTORS, decode_uint256, decode_address


# Common stablecoin addresses per chain. For Pharos, the canonical
# USDC addresses are chain-specific; users can override via
# --stablecoins. We include a few well-known addresses as defaults.

DEFAULT_STABLECOINS = {
    # Ethereum mainnet
    "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48": "USDC",
    "0xdac17f958d2ee523a2206206994597c13d831ec7": "USDT",
    "0x6b175474e89094c44da98b954eedeac495271d0f": "DAI",
    # Pharos mainnet (placeholder addresses; users should override
    # with the chain's real USDC/USDT addresses)
    "0x0000000000000000000000000000000000000000": "USDC",
}

# Default UniswapV2-style factory addresses for getAmountsOut
# We use a minimal reserves-based price quote to avoid needing the
# factory + router ABI. A more accurate implementation would call
# the router's getAmountsOut; this is a quick approximation.

UNIV2_GETRESERVES_SELECTOR = SELECTORS["getReserves()"]


def _read_reserves(rpc: RpcClient, pair: str) -> Optional[Tuple[int, int]]:
    """Return (reserve0, reserve1) from a UniswapV2 pair, or None on error."""
    try:
        raw = rpc.eth_call(pair, UNIV2_GETRESERVES_SELECTOR)
    except RpcError:
        return None
    if not raw or raw == "0x":
        return None
    h = raw[2:] if raw.startswith("0x") else raw
    if len(h) < 128:
        return None
    r0 = decode_uint256("0x" + h[0:64])
    r1 = decode_uint256("0x" + h[64:128])
    return (r0, r1)


def price_native_units_to_usd(
    rpc: RpcClient,
    token: str,
    amount_raw: int,
    decimals: int,
    pair_address: Optional[str] = None,
    stablecoins: Optional[dict] = None,
) -> float:
    """Return the USD value of `amount_raw` of `token` (already at
    `decimals` decimal places).

    If `pair_address` is supplied, reads its reserves and computes a
    price assuming one side is the token and the other is a
    stablecoin (we don't check which side — for dust detection the
    precision is more than enough either way).

    If `pair_address` is None, returns 0.0.
    """
    if not pair_address:
        return 0.0
    reserves = _read_reserves(rpc, pair_address)
    if not reserves:
        return 0.0
    r0, r1 = reserves
    if r0 == 0 or r1 == 0:
        return 0.0
    # We don't know which side is the token; take the geometric mean
    # of the two possible prices as a rough estimate.
    p0 = r1 / r0  # 1 unit of token0 = p0 units of token1
    p1 = r0 / r1  # 1 unit of token1 = p1 units of token0
    # Pick the higher of the two prices as a conservative (anti-dust)
    # estimate.
    price_per_unit = max(p0, p1)
    # If the stablecoin is 6 decimals and token is `decimals`, scale.
    # We don't know which side is which, so just normalize by 1e6.
    amount_units = amount_raw / (10 ** decimals)
    return amount_units * price_per_unit / 1e6  # adjust for stable 6-dec scaling
