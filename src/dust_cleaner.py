"""
dust_cleaner.py - CLI entry point.

Usage:
  python dust_cleaner.py --wallet 0x... --rpc-url https://...
                         [--token-list tokens.json]
                         [--native-price-usd 0.42]
                         [--buffer 1.5] [--format json]
"""
from __future__ import annotations
import argparse
import json
import sys
import time
from typing import Any, Dict, List, Optional

from rpc import RpcClient, RpcError
from tokens import (
    load_token_list,
    scan_with_list,
    scan_via_logs,
    TokenHolding,
)
from gas import quote as gas_quote, DEFAULT_GAS_UNITS_ERC20
from detector import analyze, DustReport


def _report_to_dict(rep: DustReport) -> Dict[str, Any]:
    return {
        "wallet":         rep.wallet,
        "chain_id":       rep.chain_id,
        "total":          rep.total,
        "dust_count":     rep.dust_count,
        "small_count":    rep.small_count,
        "ok_count":       rep.ok_count,
        "noprice_count":  rep.noprice_count,
        "dust_value_usd": rep.dust_value_usd,
        "hygiene_score":  rep.hygiene_score,
        "gas_quote":      rep.gas_quote,
        "tokens": [
            {
                "address":            t.address,
                "symbol":             t.symbol,
                "decimals":           t.decimals,
                "balance":            t.balance,
                "value_usd":          t.value_usd,
                "price_per_unit_usd": t.price_per_unit_usd,
                "transfer_cost_usd":  t.transfer_cost_usd,
                "ratio":              t.ratio,
                "verdict":            t.verdict,
                "action":             t.action,
            }
            for t in rep.tokens
        ],
    }


def run(args: argparse.Namespace) -> Dict[str, Any]:
    rpc = RpcClient(args.rpc_url)
    try:
        chain_id = rpc.chain_id()
    except RpcError as e:
        raise SystemExit(f"error: cannot reach RPC: {e}")

    # 1. Discover holdings
    if args.token_list:
        try:
            tokens = load_token_list(args.token_list)
        except Exception as e:  # noqa: BLE001
            raise SystemExit(f"error reading token list: {e}")
        print(f"[+] Loaded {len(tokens)} tokens from {args.token_list}", file=sys.stderr)
        holdings = scan_with_list(rpc, args.wallet, tokens)
    else:
        print(f"[+] Auto-discovering tokens via Transfer logs (last {args.block_count} blocks)…", file=sys.stderr)
        holdings = scan_via_logs(rpc, args.wallet, args.block_count)

    # 2. Gas quote
    try:
        gq = gas_quote(rpc, gas_units=args.gas_units, native_price_usd=args.native_price_usd)
    except RpcError as e:
        raise SystemExit(f"error: gas oracle failed: {e}")

    # 3. Load optional pair map (token_address -> pair_address) for on-chain prices
    pair_for_token = None
    if args.pair_map:
        try:
            with open(args.pair_map) as f:
                raw = json.load(f)
            pair_for_token = {k.lower(): v for k, v in raw.items()}
        except Exception as e:  # noqa: BLE001
            print(f"[!] could not read pair map: {e}", file=sys.stderr)

    # 4. Classify
    report = analyze(
        rpc,
        args.wallet,
        holdings,
        gq,
        pair_for_token=pair_for_token,
        buffer=args.buffer,
        min_value_usd=args.min_value_usd,
    )
    return _report_to_dict(report)


def main():
    p = argparse.ArgumentParser(description="Identify dust ERC-20 tokens in a wallet.")
    p.add_argument("--wallet", required=True, help="0x address to analyze")
    p.add_argument("--rpc-url", required=True, help="JSON-RPC endpoint")
    p.add_argument("--token-list", default=None, help="Path to JSON token list (skips auto-discovery)")
    p.add_argument("--block-count", type=int, default=5000, help="Blocks to scan for auto-discovery")
    p.add_argument("--gas-units", type=int, default=DEFAULT_GAS_UNITS_ERC20, help="Override gas cost of an ERC-20 transfer")
    p.add_argument("--buffer", type=float, default=1.5, help="Multiplier on gas cost before flagging as dust")
    p.add_argument("--min-value-usd", type=float, default=0.0, help="Ignore tokens below this USD")
    p.add_argument("--native-price-usd", type=float, default=0.0, help="USD price of the native gas token (e.g. PROS)")
    p.add_argument("--pair-map", default=None, help="JSON file mapping token address -> UniswapV2 pair address")
    p.add_argument("--format", choices=["text", "json", "markdown", "html"], default="text")
    p.add_argument("--out", default="-")
    args = p.parse_args()

    payload = run(args)

    if args.format == "json":
        out = json.dumps(payload, indent=2)
    elif args.format == "markdown":
        from report import render_markdown
        out = render_markdown(payload)
    elif args.format == "html":
        from report import render_html
        out = render_html(payload)
    else:
        from report import render_text
        out = render_text(payload, use_color=sys.stdout.isatty())

    if args.out == "-":
        sys.stdout.write(out)
    else:
        with open(args.out, "w") as f:
            f.write(out)


if __name__ == "__main__":
    main()
