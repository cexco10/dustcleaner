# Dust thresholds

This file documents how `src/detector.py` decides whether a token
holding is "dust". The math is intentionally simple so the rule
can be explained to anyone in one sentence.

## Definition

A token holding is **DUST** if the USD value of the balance is less
than the USD cost of gas to transfer it, multiplied by a buffer:

```
is_dust  =  balance_USD  <  gas_cost_USD  *  buffer
```

Default `buffer = 1.5`. The buffer covers:

- EIP-1559 base fee variance between estimate and inclusion.
- Slippage / gas-price drift during the few minutes between scan
  and execution.
- The risk of a failed transfer wasting the gas anyway.

## Verdict bands

| Band      | Condition                          | Recommended action |
|-----------|------------------------------------|--------------------|
| `DUST`    | `value / transfer_cost < buffer`   | Ignore or sweep to a dust-collector |
| `SMALL`   | `buffer <= value / transfer_cost < 5` | Bundle into a single sweep tx |
| `OK`      | `value / transfer_cost >= 5`       | Normal handling    |
| `NO_PRICE`| `value == 0` (price oracle missed) | Manually review    |

The 5× threshold for `SMALL` is a heuristic: if it costs you $0.10
to move a token worth $0.50, the ratio is 5× and it's a borderline
case. Bundle it with other SMALL tokens to amortize the gas.

## Wallet hygiene score

```
hygiene_score = 100 * (1 - dust_count / total_count)
clamped to [0, 100]
```

- **100** — no dust at all. Pristine.
- **80-99** — a few dust tokens, normal for an active wallet.
- **50-79** — heavy dust accumulation, recommend a sweep.
- **0-49** — wallet is mostly dust; consider migrating to a fresh
  address.

Tokens with `NO_PRICE` are excluded from the score (we don't want
unverifiable tokens to falsely deflate or inflate the metric).

## Worked example

Suppose:

- ETH = $3,000
- `gas_price_wei` = 30 gwei = 30 × 10⁹ wei
- `gas_units` = 65,000 (default ERC-20 transfer)

Then:

```
gas_cost_native  = 30e9 * 65_000 / 1e18  = 0.00195 ETH
gas_cost_usd     = 0.00195 * 3000        = $5.85
```

For each token:

| Token | Balance | Price (USD) | Value (USD) | Ratio | Verdict |
|-------|---------|-------------|-------------|-------|---------|
| USDC  | 5.0     | 1.00        | 5.00        | 0.85  | DUST    |
| SHIB  | 1,000,000 | 0.00002   | 20.00       | 3.42  | SMALL   |
| WBTC  | 0.001   | 65,000     | 65.00       | 11.1  | OK      |
| ???   | 100     | 0          | 0           | 0     | NO_PRICE|

Hygiene score: `100 * (1 - 1/4) = 75`.

## Why not "below $X" alone?

Many wallet tools flag tokens below a fixed USD threshold (e.g.
$1). This skill deliberately uses a **value-vs-cost** comparison
because:

1. On a $5-gwei chain, a $1 token is fine to transfer; on a
   $300-gwei chain (post-shock), the same $1 token is dust.
2. The user's intent is "is it worth my time and gas?" — that
   question is value-vs-cost, not value-alone.
3. A 1.5× buffer gives a defensible "ignore this" rule that
   doesn't require the user to think about gas.

## Edge cases the threshold does NOT catch

- **Transfer-fee tokens** (e.g. PAXG) — the gas cost of a transfer
  is dominated by the *token's* transfer fee, not the chain gas.
  Override `--gas-units` or manually exclude these tokens.
- **Approval-required tokens** — if you've never approved the
  spender, the first transfer costs more (an `approve` tx + a
  `transferFrom` tx). The skill does not detect this.
- **Phishing airdrops** — the skill doesn't check whether the
  token is verified or known. Run a separate contract-verification
  pass on the dust list before sweeping.
