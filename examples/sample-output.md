# Example: Dust Report

> Generated against a sample wallet on Pharos mainnet. See `SKILL.md`
> for the full command line.

```
================================================================
  DUST REPORT — 0xA1B2C3D4E5F60718293A4B5C6D7E8F9012345678
  Chain ID: 1672
================================================================

  Gas oracle
    gas price:        1,000,000,000 wei
    gas units:        65,000 (ERC-20 transfer)
    native price USD: $0.4200
    cost / transfer:  $0.000027

  Tokens scanned: 4
    DUST:      2  ($0.4200 value)
    SMALL:     1
    OK:        1
    NO_PRICE:  0

  >>> WALLET HYGIENE SCORE: 50 / 100 <<<

  Per-token detail
  ------------------------------------------------------------
  [   SMALL] AAA       bal=           100  value=$    0.1000  ratio=  3.66
             addr=0xtok1…
             → Bundle into a single sweep transaction with other SMALL tokens.
  [    DUST] BBB       bal=            50  value=$    0.0500  ratio=  1.83
             addr=0xtok2…
             → Ignore. Sweep to a dust-collector if you want to consolidate.
  [      OK] CCC       bal=         1,000  value=$    1.0000  ratio= 36.6
             addr=0xtok3…
             → Normal handling — transferable at any time.
  [    DUST] DDD       bal=             5  value=$    0.0050  ratio=  0.18
             addr=0xtok4…
             → Ignore. Sweep to a dust-collector if you want to consolidate.
```

## Reading the report

- **Wallet hygiene score** is 0–100, higher is better. 50 means half
  the tokens in the wallet are dust.
- **DUST** means the value of the balance is less than 1.5× the
  gas cost of transferring it. Don't bother moving these.
- **SMALL** means it's worth more than the gas, but not by much
  (< 5×). Bundle with other SMALL tokens to amortize the gas.
- **OK** means the token is at least 5× the gas cost. Normal
  handling.
- **NO_PRICE** means the engine couldn't find a price quote for
  the token. Review the contract manually before sweeping.

## Next steps for the user

1. **DUST** tokens — ignore, or sweep via a dust-collector
   contract (e.g. UniFi, Benqi dust sweeper) to consolidate.
2. **SMALL** tokens — combine into a single sweep transaction.
3. **OK** tokens — keep; transfer normally.
4. **NO_PRICE** tokens — check the contract on a block explorer
   before doing anything. Could be a phishing airdrop.
