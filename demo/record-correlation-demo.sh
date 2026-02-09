#!/usr/bin/env bash
# Record a short demo showing --endpoint-id and --session-id (correlation support).
# Use for a GIF that shows multi-session/metadata without implying full orchestrator.
# Run from repo root: asciinema rec demo/correlation-demo.cast -c "bash demo/record-correlation-demo.sh"

set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PATH="$ROOT/python/.venv/bin:$PATH"

echo "=== Correlation metadata demo (--endpoint-id / --session-id) ==="
echo ""
echo "Recording with --endpoint-id filesystem --session-id run-demo-1 ..."
agent-vcr record --transport stdio \
  --server-command "python demo/servers/calculator_v1.py" \
  -o demo/correlation-session.vcr \
  --demo \
  --endpoint-id filesystem \
  --session-id run-demo-1
echo ""
echo "Inspect (metadata shows endpoint_id and session_id):"
agent-vcr inspect demo/correlation-session.vcr --format table
echo ""
echo "Done. Use: agg demo/correlation-demo.cast assets/correlation-demo.gif"
