---
name: dust-token-cleaner
description: >
  REQUIRED for any task that requires identifying "dust" ERC-20 tokens
  in a wallet — tokens whose USD value is so low that the gas cost of
  transferring them exceeds the value of the tokens themselves. Invoke
  when the user asks to "find dust tokens", "clean up my wallet",
  "what tokens are below the gas threshold", "which tokens are not
  worth transferring", "small balance tokens", "wallet hygiene", or
  wants a per-token breakdown of (balance, USD value, gas cost to
  transfer, dust verdict). Use the bundled `src/dust_cleaner.py`
  engine to scan a wallet's token holdings via JSON-RPC (works with
  any EVM-compatible RPC URL, including Pharos Pacific mainnet and
  Atlantic testnet).
  Do not attempt dust detection without reading this skill.
version: 0.1.0
requires:
  - python >= 3.9
  - requests
  - anyBins:
      - cast   # optional, used for manual cross-check of balances
      - jq     # optional, used for ergonomic RPC URL extraction
---

# Dust Token Cleaner

Identify ERC-20 tokens in a wallet whose **balance is worth less than
the gas cost of transferring them** — the classic "dust" problem.

The skill ships a Python engine that:

1. Reads a token list (user-supplied or auto-discovered via a
   Pharos-compatible token list / known token registry).
2. For each token, calls `balanceOf(wallet)` and `decimals()` to get
   the spendable balance.
3. Fetches a USD price per token (default: a UniswapV2-style on-chain
   quote; fall back to 0 with a warning).
4. Fetches the current gas cost in USD: `gas_units * gas_price_native
   * native_price_USD`.
5. Flags any token whose `balance_USD < gas_cost_USD * buffer` as
   **DUST**, with a label and a recommended action.

## When to use

- The user asks "what tokens in my wallet are worth less than the
  gas to move them?"
- The user wants a wallet-hygiene sweep before a tax-loss harvest.
- The user wants to know which tokens they can safely ignore.
- The user wants to batch-evaluate a list of candidate tokens
  (without supplying the wallet).

## When NOT to use

- Native-token dust (this skill focuses on ERC-20; native balance
  is reported separately as context).
- NFT dust (use a separate NFT-floor tool).
- Spam-token identification based on contract verification status
  (out of scope; the skill only does the value-vs-gas math).

## Inputs

| Input           | Required | Description                                            |
|-----------------|----------|--------------------------------------------------------|
| `wallet`        | yes      | 0x address to analyze                                  |
| `rpc_url`       | yes      | JSON-RPC endpoint (any EVM-compatible chain)           |
| `token_list`    | no       | Path to a JSON file of {address, symbol?, decimals?}   |
| `gas_units`     | no       | Override gas cost of an ERC-20 transfer (default 65000) |
| `buffer`        | no       | Multiplier on gas cost before flagging as dust (default 1.5) |
| `min_value_usd` | no       | Ignore tokens already known to be < this USD (default 0) |
| `format`        | no       | `text` (default), `json`, `markdown`, `html`           |

## Outputs

A structured report with:

- Per-token detail: symbol, decimals, balance, USD value, gas cost
  to transfer, dust verdict, recommended action.
- An aggregate summary: total token count, dust count, dust USD
  value, dust native-gas equivalent.
- A "wallet hygiene score" 0–100 (fewer dust tokens = higher score).

### Verdicts

| Verdict     | Meaning                                                | Recommended action |
|-------------|--------------------------------------------------------|--------------------|
| `DUST`      | `balance_USD < gas_cost_USD * buffer`                  | Ignore or sweep to dust converter |
| `SMALL`     | `balance_USD < 5 * gas_cost_USD` (not full dust)       | Bundle into a single sweep tx |
| `OK`        | `balance_USD >= 5 * gas_cost_USD`                      | Normal handling |
| `NO_PRICE`  | Could not determine USD value (no on-chain quote)      | Manually review    |

## Quick start

```bash
# 1. Install
pip install -r requirements.txt

# 2. Scan a wallet on Pharos mainnet
python src/dust_cleaner.py \
  --wallet 0xYourWallet \
  --rpc-url https://rpc.pharos.xyz \
  --token-list tokens.example.json

# 3. Get a JSON report
python src/dust_cleaner.py \
  --wallet 0xYourWallet \
  --rpc-url https://rpc.pharos.xyz \
  --token-list tokens.example.json \
  --format json > dust-report.json
```

## Agent invocation pattern

When the user asks for a dust sweep, the Agent should:

1. Resolve the RPC URL — accept the user's URL, or use a known EVM
   RPC for the chain the user mentions.
2. Ask the user for the wallet address (never invent one).
3. Ask the user for a token list, OR auto-discover via a known
   token registry (Pharos maintains a public list at
   `https://token-list.pharos.xyz/` — substitute as appropriate).
4. Run `src/dust_cleaner.py` with the parameters above.
5. Pipe the JSON output through `src/report.py` for a formatted
   report.
6. Present the verdict, count, and total dust value as the headline.

## Error handling

| Error                         | Cause                            | Action |
|-------------------------------|----------------------------------|--------|
| `rpc unreachable`             | Bad / dead RPC URL               | Ask user for a working RPC |
| `no tokens found`             | Empty or unreadable token list   | Supply a token list with at least one address |
| `price quote failed`          | Token has no on-chain liquidity  | Mark `NO_PRICE`, do not flag as dust |
| `gas oracle failed`           | `eth_gasPrice` rejected          | Fall back to a chain-specific default |

## Limitations

- On-chain price quotes are best-effort. Tokens with no liquidity on
  a known DEX cannot be valued; they're marked `NO_PRICE` and
  excluded from the dust verdict.
- The default gas cost of 65,000 units assumes a plain ERC-20
  `transfer`. Tokens with transfer fees, rebasing, or non-standard
  decimals may differ.
- The buffer (default 1.5) covers only gas; it does not account for
  the opportunity cost of holding dust tokens or the rug-pull risk
  of unknown contracts.
