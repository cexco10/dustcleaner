"""
tokens.py - Discover ERC-20 holdings and read balances.

Two modes:

  1. User-supplied token list (a JSON file with [{address, symbol?,
     decimals?}, ...]). The skill reads balanceOf for each.

  2. Auto-discovery via Transfer event log scan. Walks the last N
     blocks looking for ERC-20 Transfer events involving the wallet,
     then dedupes the token addresses and reads their balances. This
     is the heavy mode and should be used sparingly.

ERC-20 minimal ABI fragments are precomputed in `rpc.py`.
"""
from __future__ import annotations
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from rpc import (
    RpcClient,
    RpcError,
    encode_balanceOf,
    encode_decimals,
    encode_symbol,
    decode_uint256,
    decode_string,
    SELECTORS,
)


TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"


@dataclass
class TokenHolding:
    address: str
    symbol: str = "???"
    decimals: int = 18
    balance_raw: int = 0

    @property
    def balance(self) -> float:
        return self.balance_raw / (10 ** self.decimals) if self.decimals else float(self.balance_raw)


def load_token_list(path: str) -> List[Dict[str, Any]]:
    """Load a JSON file of {address, symbol?, decimals?}.

    Accepts both `[...]` and `{"tokens": [...]}` shapes.
    """
    with open(path) as f:
        data = json.load(f)
    if isinstance(data, dict) and "tokens" in data:
        data = data["tokens"]
    if not isinstance(data, list):
        raise ValueError("token list must be a JSON array")
    out = []
    for t in data:
        if not isinstance(t, dict):
            continue
        addr = (t.get("address") or t.get("addr") or "").lower()
        if not addr.startswith("0x") or len(addr) != 42:
            continue
        out.append({
            "address": addr,
            "symbol":  t.get("symbol") or "",
            "decimals": t.get("decimals"),
        })
    return out


def _read_decimals(rpc: RpcClient, token: str) -> int:
    try:
        raw = rpc.eth_call(token, encode_decimals())
        return decode_uint256(raw)
    except RpcError:
        return 18  # safe default


def _read_symbol(rpc: RpcClient, token: str) -> str:
    try:
        raw = rpc.eth_call(token, encode_symbol())
        return decode_string(raw) or "???"
    except RpcError:
        return "???"


def _read_balance(rpc: RpcClient, token: str, holder: str) -> int:
    try:
        raw = rpc.eth_call(token, encode_balanceOf(holder))
        return decode_uint256(raw)
    except RpcError:
        return 0


def scan_with_list(
    rpc: RpcClient, wallet: str, tokens: List[Dict[str, Any]]
) -> List[TokenHolding]:
    """Read balanceOf for every token in `tokens`."""
    out: List[TokenHolding] = []
    for t in tokens:
        addr = t["address"]
        sym  = t.get("symbol") or _read_symbol(rpc, addr)
        dec  = t.get("decimals")
        if dec is None:
            dec = _read_decimals(rpc, addr)
        bal = _read_balance(rpc, addr, wallet)
        out.append(TokenHolding(
            address=addr,
            symbol=sym,
            decimals=dec,
            balance_raw=bal,
        ))
    return out


def scan_via_logs(
    rpc: RpcClient, wallet: str, block_count: int = 5000
) -> List[TokenHolding]:
    """Walk the last N blocks for Transfer events involving `wallet`,
    dedupe token addresses, then read balances + metadata."""
    wallet_lc = wallet.lower()
    wallet_topic = "0x" + wallet_lc[2:].rjust(64, "0")
    head = rpc.block_number()
    start = max(0, head - block_count)
    seen_tokens: Set[str] = set()

    CHUNK = 500
    cur = start
    while cur <= head:
        end = min(cur + CHUNK - 1, head)
        try:
            logs = rpc.call("eth_getLogs", [{
                "fromBlock": hex(cur),
                "toBlock":   hex(end),
                "topics": [TRANSFER_TOPIC, None, [wallet_topic, None]],  # to OR from
            }])
        except RpcError:
            cur = end + 1
            continue
        for lg in logs:
            tok = (lg.get("address") or "").lower()
            if tok and tok not in seen_tokens:
                seen_tokens.add(tok)
        cur = end + 1

    holdings: List[TokenHolding] = []
    for addr in seen_tokens:
        sym  = _read_symbol(rpc, addr)
        dec  = _read_decimals(rpc, addr)
        bal  = _read_balance(rpc, addr, wallet)
        holdings.append(TokenHolding(
            address=addr,
            symbol=sym,
            decimals=dec,
            balance_raw=bal,
        ))
    return holdings
