# Gas math

This file documents how `src/gas.py` computes the USD cost of a
single ERC-20 transfer, and the assumptions baked into the
defaults.

## Formula

```
gas_cost_native  =  gas_price_wei  *  gas_units  /  1e18
gas_cost_usd     =  gas_cost_native  *  native_price_usd
```

- `gas_price_wei` — current network gas price in wei (legacy). Read
  from `eth_gasPrice`. For EIP-1559 chains this is `max_fee_per_gas`
  in practice; using legacy keeps the math simple and is a fair
  upper bound.
- `gas_units` — gas consumed by a single ERC-20 `transfer(address,uint256)`
  call. Default 65,000. Most modern chains (post-Istanbul) charge
  exactly 65,063 for a plain transfer; we round to 65,000.
- `native_price_usd` — USD value of one unit of native gas token
  (e.g. PROS on Pharos mainnet). Must be supplied via
  `--native-price-usd`. The engine does **not** maintain its own
  price feed for the native token.

## Why not EIP-1559 base + priority?

We could read `eth_maxPriorityFeePerGas` and add the latest base
fee, but:

1. The skill runs at scan time, not execution time. The base fee
   will move before the user actually sends a tx.
2. The 1.5× dust buffer already covers this variance.
3. A future version could read a few recent blocks and project
   the median base fee; open an issue if you need it.

## Pharos-specific note

On Pharos mainnet, the native token is **PROS** (chainId 1672).
On Pharos Atlantic testnet, the native token is **PHRS** (chainId
688689). Both are 18-decimal ERC-20-compatible tokens. When you
run the skill on Pharos, supply `--native-price-usd` with the
real-world USD value of the relevant token (or `0` to skip
USD-value verdicts and report ratio-only).

## Worked example

Suppose:

- chain = Pharos mainnet
- `gas_price_wei` = 1,000,000,000 (1 gwei)
- `gas_units` = 65,000
- `native_price_usd` = 0.42 (hypothetical PROS price)

Then:

```
gas_cost_native  = 1e9 * 65_000 / 1e18   = 0.000065 PROS
gas_cost_usd     = 0.000065 * 0.42        = $0.0000273
```

A token balance worth less than `$0.0000273 * 1.5 = $0.0000410`
would be flagged as **DUST**.

On Ethereum mainnet, with `gas_price_wei` = 30 gwei and ETH = $3000:

```
gas_cost_native  = 30e9 * 65_000 / 1e18  = 0.00195 ETH
gas_cost_usd     = 0.00195 * 3000         = $5.85
```

A token worth less than `$5.85 * 1.5 = $8.78` is dust. A very
different threshold — the same definition, a very different
outcome.

## Limitations

- The native-token price is a single point-in-time snapshot. Real
  workflows should refresh right before execution.
- The 65,000 gas-unit default assumes a plain ERC-20 `transfer`.
  Tokens with transfer fees, rebasing, or non-standard decimals
  can use 80,000–120,000 gas.
- EIP-1559 chains may show a stale `eth_gasPrice` because the
  endpoint returns the legacy gas price, not `max_fee_per_gas`.
  This is a known under-estimate on busy networks.
