#!/bin/bash
set -e
SCRIPT="scripts/sweep.sh"
bash "$SCRIPT" --help >/dev/null
if bash "$SCRIPT --demo" | grep -q "VERDICT"; then
  echo "OK: demo"
else
  echo "FAIL"; exit 1
fi
echo "All passed."
