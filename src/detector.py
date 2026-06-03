"""
detector.py - Dust detection logic.

Verdict rules
=============

For each token holding we compute:

  value_usd      = balance * price_per_unit
  transfer_usd   = gas_cost_native * native_price_usd   (= gas_units * gas_price_native / 1e18 * native_price_usd)
  ratio          = value_usd / transfer_usd

Verdict:

  - NO_PRICE:   price_per_unit unknown (no on-chain quote)
  - DUST:       ratio < buffer   (default buffer = 1.5)
  - SMALL:      buffer <= ratio < 5   (worth bundling, not single-tx)
  - OK:         ratio >= 5

Wallet hygiene score
====================

  score = 100 * (1 - dust_count / total_count)
  clamped to [0, 100].

A wallet with 0 dust is a perfect 100; a wallet with all dust is a 0.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional

from tokens import TokenHolding
from gas import GasQuote, DEFAULT_GAS_UNITS_ERC20
from prices import price_native_units_to_usd
from rpc import RpcClient


VERDICT_DUST   = "DUST"
VERDICT_SMALL  = "SMALL"
VERDICT_OK     = "OK"
VERDICT_NOPRICE = "NO_PRICE"


@dataclass
class TokenVerdict:
    address: str
    symbol: str
    decimals: int
    balance: float
    value_usd: float           # 0 if NO_PRICE
    price_per_unit_usd: float  # 0 if unknown
    transfer_cost_usd: float
    ratio: float               # 0 if NO_PRICE
    verdict: str
    action: str


@dataclass
class DustReport:
    wallet: str
    chain_id: int
    total: int
    dust_count: int
    small_count: int
    ok_count: int
    noprice_count: int
    dust_value_usd: float
    hygiene_score: int
    gas_quote: dict
    tokens: List[TokenVerdict] = field(default_factory=list)


def _classify(ratio: float, buffer: float) -> str:
    if ratio < buffer:
        return VERDICT_DUST
    if ratio < 5.0:
        return VERDICT_SMALL
    return VERDICT_OK


def _action(verdict: str) -> str:
    return {
        VERDICT_DUST:    "Ignore. Sweep to a dust-collector if you want to consolidate.",
        VERDICT_SMALL:   "Bundle into a single sweep transaction with other SMALL tokens.",
        VERDICT_OK:      "Normal handling — transferable at any time.",
        VERDICT_NOPRICE: "Could not determine USD value. Manually review the contract before sweeping.",
    }.get(verdict, "")


def analyze(
    rpc: RpcClient,
    wallet: str,
    holdings: List[TokenHolding],
    gas_quote: GasQuote,
    *,
    pair_for_token: Optional[dict] = None,
    buffer: float = 1.5,
    min_value_usd: float = 0.0,
) -> DustReport:
    """Classify every holding and assemble a DustReport."""
    chain_id = rpc.chain_id()
    pair_for_token = pair_for_token or {}
    transfer_usd = gas_quote.gas_cost_usd

    verdicts: List[TokenVerdict] = []
    dust_count = small_count = ok_count = noprice_count = 0
    dust_value_usd = 0.0

    for h in holdings:
        if h.balance_raw == 0:
            continue
        pair = pair_for_token.get(h.address.lower())
        if pair:
            usd = price_native_units_to_usd(
                rpc, h.address, h.balance_raw, h.decimals, pair_address=pair
            )
        else:
            usd = 0.0
        ratio = (usd / transfer_usd) if (transfer_usd > 0 and usd > 0) else 0.0
        price_per_unit = (usd / h.balance) if h.balance > 0 else 0.0

        if usd == 0.0:
            verdict = VERDICT_NOPRICE
            noprice_count += 1
        else:
            if usd < min_value_usd:
                # Below the user's absolute USD filter; treat as dust
                verdict = VERDICT_DUST
                dust_count += 1
                dust_value_usd += usd
            else:
                verdict = _classify(ratio, buffer)
                if verdict == VERDICT_DUST:
                    dust_count += 1
                    dust_value_usd += usd
                elif verdict == VERDICT_SMALL:
                    small_count += 1
                else:
                    ok_count += 1

        verdicts.append(TokenVerdict(
            address=h.address,
            symbol=h.symbol,
            decimals=h.decimals,
            balance=h.balance,
            value_usd=usd,
            price_per_unit_usd=price_per_unit,
            transfer_cost_usd=transfer_usd,
            ratio=ratio,
            verdict=verdict,
            action=_action(verdict),
        ))

    total = dust_count + small_count + ok_count + noprice_count
    if total == 0:
        score = 100
    else:
        score = max(0, min(100, int(100 * (1 - dust_count / total))))

    return DustReport(
        wallet=wallet,
        chain_id=chain_id,
        total=total,
        dust_count=dust_count,
        small_count=small_count,
        ok_count=ok_count,
        noprice_count=noprice_count,
        dust_value_usd=dust_value_usd,
        hygiene_score=score,
        gas_quote={
            "gas_price_wei": gas_quote.gas_price_wei,
            "gas_units": gas_quote.gas_units,
            "native_price_usd": gas_quote.native_price_usd,
            "gas_cost_native": gas_quote.gas_cost_native,
            "gas_cost_usd": gas_quote.gas_cost_usd,
        },
        tokens=verdicts,
    )
