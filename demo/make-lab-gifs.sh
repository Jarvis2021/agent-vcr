#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────
# Run commands for a single TUTORIAL lab (1–12) for asciinema → GIF.
# Usage: asciinema rec demo/lab-N.cast -c "bash demo/make-lab-gifs.sh N"
# Run from repository root.
# ──────────────────────────────────────────────────────────────────────

set -e

LAB="${1:-1}"
# Ensure we're in repo root (parent of demo/)
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RESET='\033[0m'

say() { echo -e "${CYAN}$*${RESET}"; }
cmd() { echo -e "${GREEN}\$ $*${RESET}"; sleep 0.2; "$@"; }
pause() { sleep "${1:-1}"; }

# Ensure agent-vcr is available (from python/)
export PATH="$ROOT/python/.venv/bin:$PATH"
if ! command -v agent-vcr &>/dev/null; then
  (cd "$ROOT/python" && uv pip install -e . -q) || true
fi

case "$LAB" in
  1)
    say "Lab 1: Your first recording (--demo)"
    cmd agent-vcr record --transport stdio --server-command "python demo/servers/calculator_v1.py" -o demo/lab1-out.vcr --demo
    pause 1
    say "Inspect the recording"
    cmd agent-vcr inspect demo/lab1-out.vcr --format table
    ;;
  2)
    say "Lab 2: Replaying a recording"
    cmd agent-vcr replay --file examples/recordings/calculator-v1.vcr --transport stdio --dry-run
    pause 1
    say "One request through replayer (piped)"
    echo '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | timeout 2 agent-vcr replay --file examples/recordings/calculator-v1.vcr --transport stdio 2>/dev/null || true
    ;;
  3)
    say "Lab 3: Diffing two recordings"
    cmd agent-vcr diff examples/recordings/calculator-v1.vcr examples/recordings/calculator-v2.vcr
    ;;
  4)
    say "Lab 4: Golden cassette"
    cmd mkdir -p cassettes
    cmd agent-vcr record --transport stdio --server-command "python demo/servers/calculator_v1.py" -o cassettes/golden.vcr --demo
    pause 0.5
    if [ -f python/tests/test_golden.py ] 2>/dev/null; then
      cmd "cd python && pytest tests/test_golden.py -v -q && cd .."
    else
      say "(Create tests/test_golden.py and run pytest — see TUTORIAL)"
    fi
    ;;
  5)
    say "Lab 5: Compatibility gates"
    cmd agent-vcr record --transport stdio --server-command "python demo/servers/calculator_v1.py" -o demo/v1-baseline.vcr --demo
    cmd agent-vcr record --transport stdio --server-command "python demo/servers/calculator_v2.py" -o demo/v2-candidate.vcr --demo
    cmd agent-vcr diff demo/v1-baseline.vcr demo/v2-candidate.vcr --fail-on-breaking
    cmd "echo Exit code: $?"
    ;;
  6)
    say "Lab 6: Error injection"
    cmd agent-vcr inspect examples/recordings/calculator-errors.vcr
    pause 0.5
    if [ -f python/tests/test_error_injection.py ] 2>/dev/null; then
      cmd "cd python && pytest tests/test_error_injection.py -v -q && cd .."
    else
      say "(See TUTORIAL for test_error_injection.py)"
    fi
    ;;
  7)
    say "Lab 7: Offline development"
    cmd agent-vcr record --transport stdio --server-command "python demo/servers/calculator_v1.py" -o demo/offline-dev.vcr --demo
    say "Replay (mock server)"
    cmd agent-vcr replay --file demo/offline-dev.vcr --transport stdio --dry-run
    ;;
  8)
    say "Lab 8: Multi-agent regression"
    cmd mkdir -p cassettes/team-search cassettes/team-writer
    cmd agent-vcr record --transport stdio --server-command "python demo/servers/calculator_v1.py" -o cassettes/team-search/baseline.vcr --demo
    cmd agent-vcr record --transport stdio --server-command "python demo/servers/calculator_v2.py" -o demo/server-v2-candidate.vcr --demo
    cmd agent-vcr diff cassettes/team-search/baseline.vcr demo/server-v2-candidate.vcr --fail-on-breaking
    ;;
  9)
    say "Lab 9: Protocol evolution"
    cmd agent-vcr diff examples/recordings/calculator-v1.vcr examples/recordings/calculator-v2.vcr
    if [ -f track_evolution.py ] 2>/dev/null; then
      cmd python track_evolution.py
    fi
    ;;
  10)
    say "Lab 10: Programmatic recording"
    cmd "cd python && uv run python ../examples/python/create_sample_recording.py ../demo/programmatic-sample.vcr && cd .."
    cmd agent-vcr inspect demo/programmatic-sample.vcr --format table
    ;;
  11)
    say "Lab 11: Pytest integration"
    cmd "cd python && pytest tests/ -v -q -k 'vcr or format' --co -q 2>/dev/null | head -20"
    cmd "cd python && pytest tests/test_format.py -v -q -x 2>/dev/null | tail -5"
    ;;
  12)
    say "Lab 12: Full demo (record-demo.sh)"
    cmd bash demo/record-demo.sh
    ;;
  *)
    echo "Usage: bash demo/make-lab-gifs.sh <1-12>"
    exit 1
    ;;
esac

say "Done (Lab $LAB)."
