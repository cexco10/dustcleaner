#!/usr/bin/env bash
# dustcleaner — Wallet dust token sweeper (Foundry port).
#
# Scans an ERC-20 wallet for tokens with balance below a dust
# threshold, simulates the gas cost of transferring them all, and
# emits a sweep plan. This bash port is the engine-loadable Foundry
# shim; the full list-emit-transfer loop is in the Python fallback
# for ERC-777/transfer-tax tokens.
#
# Usage:
#   bash scripts/sweep.sh --demo
#   bash scripts/sweep.sh --wallet 0xWALLET --threshold 0.001 --rpc-url https://...
#   bash scripts/sweep.sh --wallet 0xWALLET --format json

set -euo pipefail

# ---- Demo works without cast ----
if [ "${1:-}" = "--demo" ] || [ "${1:-}" = "demo" ]; then
  echo ""
  echo "========================================================================"
  echo "  DUST CLEANER  (DEMO)"
  echo "  Wallet: 0xDEMO0000000000000000000000000000000000DEAD  (synthetic)"
  echo "========================================================================"
  echo ""
  echo "  Dust tokens found (3):"
  echo "    1. 0xTOK1...  bal=0.00042  symbol=PEBBLE    est gas=21k  net=-0.00004"
  echo "    2. 0xTOK2...  bal=0.00010  symbol=DUST      est gas=21k  net=-0.00005"
  echo "    3. 0xTOK3...  bal=0.00095  symbol=FRAGMENT  est gas=42k  net=-0.00010"
  echo ""
  echo "  Total dust value (USD):  0.0023"
  echo "  Total gas cost (USD):    0.0042"
  echo "  >>> VERDICT: skip  (gas > dust)  <<<"
  echo ""
  exit 0
fi

# ---- Foundry required for non-demo ----
if ! command -v cast >/dev/null 2>&1; then
  echo "Error: 'cast' not found. Install Foundry:"
  echo "  curl -L https://foundry.paradigm.xyz | bash && foundryup"
  exit 1
fi

# ---- Load network config ----
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NET_JSON="$SCRIPT_DIR/../assets/networks.json"
[ ! -f "$NET_JSON" ] && { echo "Error: $NET_JSON not found"; exit 1; }

get_field() {
  local net_name="$1" field="$2"
  sed -n "/\"name\": *\"$net_name\"/,/^    }/p" "$NET_JSON" \
    | grep -E "\"$field\":" | head -1 \
    | sed -E 's/^[^:]+:[[:space:]]*"([^"]*)".*/\1/' | sed -E 's/,$//'
}
get_num() {
  local net_name="$1" field="$2"
  sed -n "/\"name\": *\"$net_name\"/,/^    }/p" "$NET_JSON" \
    | grep -E "\"$field\":" | head -1 | grep -oE '[0-9]+' | head -1
}

# ---- Arg parsing ----
WALLET=""
RPC_URL=""
CHAIN="mainnet"
THRESHOLD="0.001"
FORMAT="text"

usage() {
  cat <<USAGE
dustcleaner — Wallet dust token sweeper (Foundry port)

Usage:
  bash scripts/sweep.sh --demo
  bash scripts/sweep.sh --wallet 0xWALLET --threshold 0.001 --rpc-url URL

Options:
  --wallet ADDR        target wallet
  --rpc-url URL        JSON-RPC endpoint
  --chain NAME         mainnet | testnet [default: mainnet]
  --threshold N        dust threshold in tokens [default: 0.001]
  --format FMT         text | json [default: text]
  --help               show this help

Prerequisites:
  - Foundry (cast): curl -L https://foundry.paradigm.xyz | bash && foundryup
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    --wallet) WALLET="$2"; shift 2 ;;
    --rpc-url) RPC_URL="$2"; shift 2 ;;
    --chain) CHAIN="$2"; shift 2 ;;
    --threshold) THRESHOLD="$2"; shift 2 ;;
    --format) FORMAT="$2"; shift 2 ;;
    -*) echo "Unknown flag: $1" >&2; usage; exit 1 ;;
    *) echo "Unknown arg: $1" >&2; usage; exit 1 ;;
  esac
done

case "$CHAIN" in
  mainnet) RPC_URL="${RPC_URL:-$(get_field mainnet rpcUrl)}"; CHAIN_ID=$(get_num mainnet chainId) ;;
  testnet) RPC_URL="${RPC_URL:-$(get_field atlantic-testnet rpcUrl)}"; CHAIN_ID=$(get_num atlantic-testnet chainId) ;;
  *) echo "Unknown chain: $CHAIN" >&2; exit 1 ;;
esac

if [ -z "$WALLET" ]; then
  echo "Error: --wallet required (or use --demo)" >&2
  usage
  exit 1
fi

# ---- Walk wallet for tokens (in a real impl, transfer events + index) ----
# The bash port surfaces the engine-loadable scaffold. For a full
# sweep, run the Python fallback: bash src/sweep.py --wallet ...
echo ""
echo "========================================================================"
echo "  DUST CLEANER"
echo "  Wallet: $WALLET"
echo "  Threshold: $THRESHOLD"
echo "  Chain: $CHAIN_ID"
echo "========================================================================"
echo ""
echo "  No live dust scan in the bash port; the full ERC-20 transfer-event"
echo "  walker is in:"
echo "    python3 src/sweep.py --wallet $WALLET --threshold $THRESHOLD \\"
echo "      --rpc-url $RPC_URL"
echo ""
echo "  For a quick cast-driven balance check, paste a token address and run:"
echo "    cast call --rpc-url $RPC_URL <TOKEN> 'balanceOf(address)(uint256)' $WALLET"
echo "    cast call --rpc-url $RPC_URL <TOKEN> 'symbol()(string)'"
echo "    cast call --rpc-url $RPC_URL <TOKEN> 'decimals()(uint8)'"
echo ""
echo "  (Then divide balance by 10**decimals to compare against --threshold.)"
echo ""
