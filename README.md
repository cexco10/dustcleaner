# DustCleaner — Dust Token Detector

> Identify ERC-20 tokens in a wallet whose **balance is worth less
> than the gas cost of transferring them** — the classic "dust"
> problem.

[![python](https://img.shields.io/badge/python-3.9%2B-blue)]()
[![license](https://img.shields.io/badge/license-MIT--0-green)]()
[![rpc](https://img.shields.io/badge/RPC-JSON--RPC%20%7C%20EVM-orange)]()

## Overview

DustCleaner reads every ERC-20 holding in a wallet, fetches the
current gas cost in USD, and flags any token whose USD value is
below the cost to transfer it (times a 1.5× safety buffer). The
output is a per-token verdict (`DUST` / `SMALL` / `OK` /
`NO_PRICE`), a wallet-hygiene score, and a recommended action per
token.

It works against any EVM-compatible JSON-RPC endpoint and ships
with first-class support for the Pharos networks (see
[Supported networks](#supported-networks)).

## Features

- **Two discovery modes** — supply a JSON token list for fast
  scanning, or auto-discover via `Transfer` event log walk.
- **Value-vs-cost verdict** — a token is dust if its USD value is
  less than the gas cost to transfer it, not just a fixed USD
  threshold.
- **Four-tier verdict** — `DUST` / `SMALL` / `OK` / `NO_PRICE` with
  a recommended action per verdict.
- **Wallet hygiene score** — 0–100, higher = less dust. Useful for
  "is this wallet worth reusing?" decisions.
- **Multi-format output** — text (with ANSI colors), JSON,
  Markdown, or HTML via the `report.py` formatter.
- **Agent-ready** — ships a `SKILL.md` at the repo root with the
  invocation contract an agent runtime needs to drive the tool.
- **Pluggable price oracle** — default reads UniswapV2 reserves;
  swap in a real oracle (Chainlink, Pyth, CoinGecko) by replacing
  `src/prices.py:price_native_units_to_usd`.

## Supported networks

The tool runs against any EVM-compatible JSON-RPC endpoint. The
following networks are explicitly supported out of the box and used
in the examples below.

| Network                 | Chain ID | RPC URL                                | Native token | Explorer                          |
|-------------------------|----------|----------------------------------------|--------------|-----------------------------------|
| Pharos Pacific Mainnet  | `1672`   | `https://rpc.pharos.xyz`               | PROS         | https://www.pharosscan.xyz/       |
| Pharos Atlantic Testnet | `688689` | `https://atlantic.dplabs-internal.com` | PHRS         | https://atlantic.pharosscan.xyz/  |

You can target either by passing the matching `--rpc-url` flag
(see [Usage](#usage)).

## Framework

- **Language:** Python 3.9+
- **RPC protocol:** JSON-RPC (`eth_call`, `eth_gasPrice`,
  `eth_blockNumber`, `eth_chainId`, `eth_getLogs`)
- **External CLIs (optional):** `cast` from
  [Foundry](https://book.getfoundry.xyz/) for manual cross-checks
  of balances; `jq` for ergonomic RPC URL extraction in shell
  pipelines.
- **No web3 framework required** — the engine speaks JSON-RPC
  directly over `requests` so it has the smallest possible install
  footprint.

## Dependencies

Runtime (Python):

- `requests>=2.31` — HTTP client used by `src/rpc.py`, the price
  oracle, and the token scanner.

External (only if you want the optional CLIs):

- `cast` / `forge` — Foundry CLI (https://book.getfoundry.xyz/getting-started/installation).
- `jq` — command-line JSON processor, used in README shell snippets.

Everything is pinned in `requirements.txt` at the repo root.

## Install

### 1. Install Python 3.9+ and pip

```bash
# macOS
brew install python@3.11
# Debian/Ubuntu/Termux
apt install -y python3 python3-pip
```

Verify with `python3 --version`.

### 2. (Optional) Install Foundry if you want cast/forge fallback

```bash
curl -L https://foundry.paradigm.xyz | bash
foundryup
```

Verify with `cast --version`. Foundry is OPTIONAL for this skill — the bash CLI in `scripts/cli.sh` works without it.

### 3. Get the skill

```bash
git clone https://github.com/cexco10/dustcleaner
cd dustcleaner
pip install -r requirements.txt
chmod +x scripts/*.sh
```

That's it. No build step, no native compilation. The skill is a Python 3.9+ module wrapped by a bash CLI for easy invocation.
### 1. Install Foundry (the engine the skill is built on)

```bash
curl -L https://foundry.paradigm.xyz | bash
foundryup
```

Verify with `cast --version`. This gives you `cast`, `forge`, `anvil`, and `chisel` on your `$PATH`.

### 2. Install jq (used to parse JSON)

```bash
# macOS
brew install jq
# Debian/Ubuntu/Termux
apt install -y jq
# Alpine
apk add jq
```

Verify with `jq --version`.

## Usage

### Scan a wallet on Pharos mainnet

```bash
python src/dust_cleaner.py \
  --wallet 0xYourWallet \
  --rpc-url https://rpc.pharos.xyz \
  --token-list tokens.example.json \
  --native-price-usd 0.42
```

### Scan a wallet on Pharos Atlantic testnet

```bash
python src/dust_cleaner.py \
  --wallet 0xYourWallet \
  --rpc-url https://atlantic.dplabs-internal.com \
  --token-list tokens.example.json \
  --native-price-usd 0.10
```

### Auto-discover tokens via Transfer event logs

```bash
python src/dust_cleaner.py \
  --wallet 0xYourWallet \
  --rpc-url https://rpc.pharos.xyz \
  --block-count 5000
```

### Output as JSON, then format as Markdown

```bash
python src/dust_cleaner.py \
  --wallet 0xYourWallet \
  --rpc-url https://rpc.pharos.xyz \
  --token-list tokens.example.json \
  --native-price-usd 0.42 \
  --format json \
  | python src/report.py --format markdown --out dust-report.md
```

### Output as HTML

```bash
python src/dust_cleaner.py \
  --wallet 0xYourWallet \
  --rpc-url https://rpc.pharos.xyz \
  --token-list tokens.example.json \
  --native-price-usd 0.42 \
  --format json \
  | python src/report.py --format html --out dust-report.html
```

### Token list format

A token list is a JSON file. Both `[...]` and `{"tokens": [...]}`
shapes are accepted.

```json
[
  { "address": "0xUSDC...", "symbol": "USDC", "decimals": 6 },
  { "address": "0xWETH...", "symbol": "WETH", "decimals": 18 },
  { "address": "0xARB..."  }
]
```

`symbol` and `decimals` are optional; the engine reads them on-chain
if missing.

### Command-line flags

| Flag                 | Required | Default     | Description                                          |
|----------------------|----------|-------------|------------------------------------------------------|
| `--wallet`           | yes      | —           | 0x address to analyze                                |
| `--rpc-url`          | yes      | —           | JSON-RPC endpoint                                    |
| `--token-list`       | no       | —           | Path to JSON token list                              |
| `--block-count`      | no       | 5000        | Blocks to scan for auto-discovery                    |
| `--gas-units`        | no       | 65000       | Override gas cost of an ERC-20 transfer              |
| `--buffer`           | no       | 1.5         | Multiplier on gas cost before flagging as dust       |
| `--min-value-usd`    | no       | 0           | Ignore tokens below this USD                         |
| `--native-price-usd` | no       | 0           | USD price of the native gas token (e.g. PROS)        |
| `--pair-map`         | no       | —           | JSON file mapping token address -> UniswapV2 pair    |
| `--format`           | no       | text        | `text`, `json`, `markdown`, `html`                   |
| `--out`              | no       | -           | Output file (`-` for stdout)                         |

### Sample output

See `examples/sample-output.md` for what a real report looks like.

## AI Agent Integration

This repository ships a `SKILL.md` at the root that any agent
runtime can load to discover the skill. The flow is:

1. The agent reads `SKILL.md` to learn the capability and required
   arguments (`--wallet`, `--rpc-url`).
2. The agent collects the wallet address from the user (it never
   invents one).
3. The agent collects a token list from the user, OR enables
   auto-discovery (slower, walks Transfer logs).
4. The agent runs `python src/dust_cleaner.py` with the parameters
   and captures stdout (or `--out` to a file).
5. The agent surfaces the hygiene score, dust count, and total
   dust value as the top of its reply.
6. If a formatted report is needed, the agent pipes the JSON
   output through `python src/report.py --format <fmt>`.

A typical prompt that triggers the skill:

> "Which tokens in my Pharos wallet are worth less than the gas to
> move them? Wallet is `0xYourWallet`, RPC is
> `https://rpc.pharos.xyz`."

A typical reply:

> **Wallet hygiene score: 75 / 100** — 1 DUST token worth $0.05,
> 1 SMALL token worth $0.50, 1 OK token worth $1.00. The dust
> token is `BBB` at `0xtok2…` — recommend ignoring. See
> `dust-report.md` for the full breakdown.

## Repository layout

```
dustcleaner/
├── SKILL.md                       # Agent-facing skill spec
├── README.md                      # This file
├── LICENSE                        # MIT-0
├── requirements.txt
├── src/
│   ├── dust_cleaner.py            # CLI entry point
│   ├── detector.py                # Dust verdict logic
│   ├── gas.py                     # Gas oracle (wei → USD)
│   ├── prices.py                  # Token price oracle (UniswapV2 reserves)
│   ├── tokens.py                  # ERC-20 scanner (list mode + log auto-discovery)
│   ├── rpc.py                     # JSON-RPC client
│   └── report.py                  # Text / JSON / Markdown / HTML formatter
├── references/
│   ├── dust-thresholds.md         # Verdict rules + worked example
│   └── gas-math.md                # Gas cost formula + Pharos notes
└── examples/
    └── sample-output.md           # What a real report looks like
```

## How detection works

See `references/dust-thresholds.md` for the verdict rules and
`references/gas-math.md` for the gas-cost formula.

## Roadmap

- [ ] Wire in a real price oracle (Chainlink / Pyth / CoinGecko).
- [ ] Add EIP-1559 base-fee projection (replace legacy gas price).
- [ ] Auto-derive token list from a Pharos token registry.
- [ ] Add a "sweep" mode that batches dust tokens into a single
      tx (requires a private key; off by default).

## Contributing

PRs welcome — especially new price oracles, Pharos token-registry
adapters, and benchmarks against real wallets.

## License

[MIT-0](https://opensource.org/licenses/MIT-0) — free to use, modify,
redistribute. No attribution required.

---

**Author:** cexco10
**Built with:** Python 3.9+, plain JSON-RPC, and a healthy
intolerance for spam airdrops.
