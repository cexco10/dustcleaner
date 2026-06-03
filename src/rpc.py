"""
rpc.py - JSON-RPC client for token reads and gas oracle.

Used to call `eth_call`, `eth_gasPrice`, `eth_blockNumber`, etc.
No web3 framework dependency.
"""
from __future__ import annotations
import json
import time
import requests
from typing import Any, Dict, List, Optional


class RpcError(Exception):
    pass


class RpcClient:
    def __init__(self, url: str, timeout: int = 30, max_retries: int = 4):
        self.url = url
        self.timeout = timeout
        self.max_retries = max_retries
        self._id = 0

    def call(self, method: str, params: List[Any]) -> Any:
        self._id += 1
        payload = {"jsonrpc": "2.0", "id": self._id, "method": method, "params": params}
        last_err: Optional[Exception] = None
        for attempt in range(self.max_retries):
            try:
                r = requests.post(self.url, json=payload, timeout=self.timeout)
                if r.status_code == 429 or r.status_code >= 500:
                    raise RpcError(f"HTTP {r.status_code}: {r.text[:200]}")
                data = r.json()
                if "error" in data:
                    raise RpcError(data["error"].get("message", "rpc error"))
                return data.get("result")
            except (requests.RequestException, RpcError) as e:
                last_err = e
                time.sleep(0.4 * (2 ** attempt))
        raise RpcError(f"RPC {method} failed after {self.max_retries} attempts: {last_err}")

    def eth_call(self, to: str, data: str, block: str = "latest") -> str:
        return self.call("eth_call", [{"to": to, "data": data}, block])

    def gas_price(self) -> int:
        """Return gas price in wei (legacy). For EIP-1559 chains the
        caller should use `eth_maxPriorityFeePerGas` + base fee; this
        skill uses legacy to keep the math simple."""
        return int(self.call("eth_gasPrice", []), 16)

    def block_number(self) -> int:
        return int(self.call("eth_blockNumber", []), 16)

    def chain_id(self) -> int:
        return int(self.call("eth_chainId", []), 16)


# --- Precomputed ERC-20 selectors ---

SELECTORS = {
    "balanceOf(address)":        "0x70a08231",
    "decimals()":                "0x313ce567",
    "symbol()":                  "0x95d89b41",
    "name()":                    "0x06fdde03",
    "totalSupply()":             "0x18160ddd",
    # UniswapV2: getReserves() returns (uint112,uint112,uint32)
    "getReserves()":             "0x0902f1ac",
    "token0()":                  "0x0dfe1681",
    "token1()":                  "0xd21220a7",
}


def _pad32(x: str) -> str:
    if x.startswith("0x"):
        x = x[2:]
    return x.lower().rjust(64, "0")


def encode_address(a: str) -> str:
    """Pad an address to 32 bytes (left-pad with zeros)."""
    a = a.lower()
    if a.startswith("0x"):
        a = a[2:]
    if len(a) != 40:
        raise ValueError(f"not a 20-byte address: {a}")
    return "0x" + a.rjust(64, "0")


def encode_balanceOf(holder: str) -> str:
    return SELECTORS["balanceOf(address)"] + encode_address(holder)[2:]


def encode_decimals() -> str:
    return SELECTORS["decimals()"]


def encode_symbol() -> str:
    return SELECTORS["symbol()"]


def decode_uint256(hexstr: str) -> int:
    if hexstr is None or hexstr in ("0x", "0x0", ""):
        return 0
    return int(hexstr, 16)


def decode_address(hexstr: str) -> str:
    if not hexstr:
        return "0x" + "0" * 40
    return "0x" + hexstr[-40:].lower()


def decode_string(hexstr: str) -> str:
    """Decode an ABI-encoded dynamic string (offset + length + data)."""
    if not hexstr or hexstr == "0x":
        return ""
    h = hexstr[2:] if hexstr.startswith("0x") else hexstr
    if len(h) < 128:
        return ""
    try:
        # offset at 0..32, length at 32..64
        length = int(h[64:128], 16)
        data = h[128:128 + length * 2]
        return bytes.fromhex(data).decode("utf-8", errors="replace")
    except Exception:
        return ""
