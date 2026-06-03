"""
report.py - Format a dust report for human or agent consumption.

Input: a JSON object with these top-level keys:
  - wallet, chain_id
  - total, dust_count, small_count, ok_count, noprice_count
  - dust_value_usd, hygiene_score
  - gas_quote: {gas_price_wei, gas_units, native_price_usd, gas_cost_native, gas_cost_usd}
  - tokens: [{address, symbol, decimals, balance, value_usd, price_per_unit_usd,
              transfer_cost_usd, ratio, verdict, action}, ...]
"""
from __future__ import annotations
import argparse
import json
import sys
from typing import Any, Dict


def _fmt_int(n) -> str:
    try:
        return f"{int(n):,}"
    except Exception:
        return str(n)


def _fmt_float(x, digits: int = 6) -> str:
    if x is None:
        return "-"
    if x == 0:
        return "0"
    if abs(x) < 0.0001:
        return f"{x:.6f}"
    if abs(x) < 1:
        # For sub-dollar values keep more precision
        return f"{x:,.{max(digits, 4)}f}"
    return f"{x:,.{digits}f}".rstrip("0").rstrip(".")


def _fmt_balance(b: float, decimals: int) -> str:
    if b == 0:
        return "0"
    if b < 0.0001:
        return f"{b:.3e}"
    return f"{b:,.{min(decimals, 6)}f}".rstrip("0").rstrip(".")


VERDICT_COLOR = {
    "DUST":     "\033[31m",  # red
    "SMALL":    "\033[33m",  # yellow
    "OK":       "\033[32m",  # green
    "NO_PRICE": "\033[90m",  # gray
}
RESET = "\033[0m"


def render_text(r: Dict[str, Any], use_color: bool = True) -> str:
    gq = r["gas_quote"]
    lines = []
    lines.append("=" * 64)
    lines.append(f"  DUST REPORT — {r['wallet']}")
    lines.append(f"  Chain ID: {r['chain_id']}")
    lines.append("=" * 64)
    lines.append("")
    lines.append(f"  Gas oracle")
    lines.append(f"    gas price:        {_fmt_int(gq['gas_price_wei'])} wei")
    lines.append(f"    gas units:        {_fmt_int(gq['gas_units'])} (ERC-20 transfer)")
    lines.append(f"    native price USD: ${_fmt_float(gq['native_price_usd'])}")
    lines.append(f"    cost / transfer:  ${_fmt_float(gq['gas_cost_usd'], 4)}")
    lines.append("")
    lines.append(f"  Tokens scanned: {r['total']}")
    lines.append(f"    DUST:      {r['dust_count']}  (${_fmt_float(r['dust_value_usd'])} value)")
    lines.append(f"    SMALL:     {r['small_count']}")
    lines.append(f"    OK:        {r['ok_count']}")
    lines.append(f"    NO_PRICE:  {r['noprice_count']}")
    lines.append("")
    lines.append(f"  >>> WALLET HYGIENE SCORE: {r['hygiene_score']} / 100 <<<")
    lines.append("")
    if r["tokens"]:
        lines.append("  Per-token detail")
        lines.append("  " + "-" * 60)
        for t in r["tokens"]:
            color = VERDICT_COLOR.get(t["verdict"], "") if use_color else ""
            reset = RESET if use_color else ""
            sym = t["symbol"] or "???"
            lines.append(
                f"  [{color}{t['verdict']:>8}{reset}] "
                f"{sym:<8}  bal={_fmt_balance(t['balance'], t['decimals']):>14}  "
                f"value=${_fmt_float(t['value_usd'], 4):>10}  "
                f"ratio={_fmt_float(t['ratio'], 2):>6}"
            )
            lines.append(f"             addr={t['address']}")
            lines.append(f"             → {t['action']}")
    return "\n".join(lines) + "\n"


def render_markdown(r: Dict[str, Any]) -> str:
    gq = r["gas_quote"]
    lines = []
    lines.append(f"# Dust Report — `{r['wallet']}`")
    lines.append("")
    lines.append(f"- **Chain ID:** {r['chain_id']}")
    lines.append(f"- **Gas cost / transfer:** ${_fmt_float(gq['gas_cost_usd'], 4)} "
                 f"({_fmt_int(gq['gas_units'])} gas × {_fmt_int(gq['gas_price_wei'])} wei × "
                 f"${_fmt_float(gq['native_price_usd'])}/native)")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Verdict   | Count |")
    lines.append("|-----------|-------|")
    lines.append(f"| DUST      | {r['dust_count']} |")
    lines.append(f"| SMALL     | {r['small_count']} |")
    lines.append(f"| OK        | {r['ok_count']} |")
    lines.append(f"| NO_PRICE  | {r['noprice_count']} |")
    lines.append(f"| **Total** | **{r['total']}** |")
    lines.append("")
    lines.append(f"### 🎯 Wallet hygiene score: **{r['hygiene_score']} / 100**")
    lines.append(f"### 💸 Dust USD value: **${_fmt_float(r['dust_value_usd'])}**")
    lines.append("")
    if r["tokens"]:
        lines.append("## Per-token detail")
        lines.append("")
        lines.append("| Verdict | Symbol | Balance | USD value | Ratio | Action |")
        lines.append("|---------|--------|---------|-----------|-------|--------|")
        for t in r["tokens"]:
            sym = t["symbol"] or "???"
            lines.append(
                f"| {t['verdict']} | `{sym}` | "
                f"{_fmt_balance(t['balance'], t['decimals'])} | "
                f"${_fmt_float(t['value_usd'], 4)} | "
                f"{_fmt_float(t['ratio'], 2)} | {t['action']} |"
            )
    return "\n".join(lines) + "\n"


def render_html(r: Dict[str, Any]) -> str:
    gq = r["gas_quote"]
    verdict_color = {
        "DUST":     "#d93025",
        "SMALL":    "#f9ab00",
        "OK":       "#1e8e3e",
        "NO_PRICE": "#5f6368",
    }
    rows = ""
    for t in r["tokens"]:
        sym = t["symbol"] or "???"
        vc = verdict_color.get(t["verdict"], "#202124")
        rows += (
            f"<tr>"
            f"<td style='color:{vc}; font-weight:600;'>{t['verdict']}</td>"
            f"<td><code>{sym}</code></td>"
            f"<td>{_fmt_balance(t['balance'], t['decimals'])}</td>"
            f"<td>${_fmt_float(t['value_usd'], 4)}</td>"
            f"<td>{_fmt_float(t['ratio'], 2)}</td>"
            f"<td style='font-size:12px; color:#5f6368;'>{t['action']}</td>"
            f"</tr>"
        )
    return f"""<!doctype html>
<html><head><meta charset="utf-8">
<title>Dust Report — {r['wallet']}</title>
<style>
  body {{ font: 14px/1.4 system-ui, sans-serif; max-width: 900px; margin: 32px auto; padding: 0 16px; color: #202124; }}
  h1 {{ border-bottom: 2px solid #202124; padding-bottom: 4px; }}
  .score {{ font-size: 32px; font-weight: 800; color: #1a73e8; margin: 16px 0 4px; }}
  .loss  {{ font-size: 24px; font-weight: 700; color: #d93025; margin-bottom: 16px; }}
  table  {{ border-collapse: collapse; width: 100%; margin-top: 8px; }}
  th, td {{ border: 1px solid #dadce0; padding: 6px 8px; text-align: left; font-size: 13px; vertical-align: top; }}
  th {{ background: #f8f9fa; }}
  code  {{ background: #f1f3f4; padding: 1px 4px; border-radius: 3px; }}
  .gas {{ background: #f8f9fa; border-left: 3px solid #1a73e8; padding: 8px 12px; margin-top: 16px; font-size: 13px; }}
</style></head><body>
<h1>Dust Report</h1>
<p><strong>Wallet:</strong> <code>{r['wallet']}</code><br>
<strong>Chain ID:</strong> {r['chain_id']}</p>

<p class="score">Wallet hygiene score: {r['hygiene_score']} / 100</p>
<p class="loss">Dust USD value: ${_fmt_float(r['dust_value_usd'])}</p>

<div class="gas">
<strong>Gas oracle</strong><br>
gas price: {_fmt_int(gq['gas_price_wei'])} wei<br>
gas units: {_fmt_int(gq['gas_units'])} (ERC-20 transfer)<br>
native price USD: ${_fmt_float(gq['native_price_usd'])}<br>
<strong>cost / transfer: ${_fmt_float(gq['gas_cost_usd'], 4)}</strong>
</div>

<h2>Per-token detail</h2>
<table>
<thead><tr><th>Verdict</th><th>Symbol</th><th>Balance</th><th>USD value</th><th>Ratio</th><th>Action</th></tr></thead>
<tbody>
{rows or "<tr><td colspan='6'>No tokens scanned</td></tr>"}
</tbody>
</table>
</body></html>
"""


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--in", dest="input", default="-")
    p.add_argument("--format", choices=["text", "markdown", "html", "json"], default="text")
    p.add_argument("--out", default="-")
    p.add_argument("--no-color", action="store_true")
    args = p.parse_args()

    raw = sys.stdin.read() if args.input == "-" else open(args.input).read()
    r = json.loads(raw)

    if args.format == "json":
        out = json.dumps(r, indent=2)
    elif args.format == "markdown":
        out = render_markdown(r)
    elif args.format == "html":
        out = render_html(r)
    else:
        out = render_text(r, use_color=not args.no_color)

    if args.out == "-":
        sys.stdout.write(out)
    else:
        with open(args.out, "w") as f:
            f.write(out)


if __name__ == "__main__":
    main()
