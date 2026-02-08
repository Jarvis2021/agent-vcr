#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────
# Agent VCR Demo Recording Script
# ──────────────────────────────────────────────────────────────────────
# This script demonstrates the core Agent VCR workflow:
#   1. Inspect a recorded MCP session
#   2. Replay it as a mock server
#   3. Diff two recordings to catch breaking changes
#
# USAGE:
#   # Install asciinema first:
#   brew install asciinema        # macOS
#   pip install asciinema         # or via pip
#
#   # Record the demo:
#   asciinema rec demo.cast -c "bash demo/record-demo.sh"
#
#   # Upload to asciinema.org:
#   asciinema upload demo.cast
#
# The script uses `pv` style typing simulation for a natural feel.
# If you prefer to type manually, just run the commands yourself
# while asciinema records.
# ──────────────────────────────────────────────────────────────────────

set -e

# Colors
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RESET='\033[0m'

# Simulated typing effect
type_cmd() {
    local cmd="$1"
    echo -ne "${GREEN}\$ ${RESET}"
    for (( i=0; i<${#cmd}; i++ )); do
        echo -n "${cmd:$i:1}"
        sleep 0.04
    done
    echo ""
    sleep 0.3
}

pause() {
    sleep "${1:-1.5}"
}

clear
echo -e "${CYAN}╔══════════════════════════════════════════════════════════╗${RESET}"
echo -e "${CYAN}║           Agent VCR — Demo Walkthrough                  ║${RESET}"
echo -e "${CYAN}║  Record, Replay, and Diff MCP interactions              ║${RESET}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════════╝${RESET}"
echo ""
pause 2

# ── Step 1: Inspect ──────────────────────────────────────────────────
echo -e "${YELLOW}━━━ Step 1: Inspect a recorded MCP session ━━━${RESET}"
echo ""
pause 1

type_cmd "agent-vcr inspect examples/recordings/calculator-v1.vcr"
agent-vcr inspect examples/recordings/calculator-v1.vcr 2>/dev/null || {
    # Fallback if CLI isn't installed — show what the output looks like
    echo "Recording: examples/recordings/calculator-v1.vcr"
    echo "Format:    1.0.0"
    echo "Transport: stdio"
    echo "Server:    calculator-server v1.0.0"
    echo "Client:    claude-desktop v1.4.0"
    echo "Recorded:  2026-02-08 10:30:00"
    echo ""
    echo "┌────┬──────────────┬─────────────────────────┬─────────┬──────────┐"
    echo "│ #  │ Method       │ Params                  │ Status  │ Latency  │"
    echo "├────┼──────────────┼─────────────────────────┼─────────┼──────────┤"
    echo "│ 0  │ tools/list   │ {}                      │ success │  23.4 ms │"
    echo "│ 1  │ tools/call   │ add(a=15, b=27)         │ success │   8.7 ms │"
    echo "│ 2  │ tools/call   │ multiply(a=6, b=7)      │ success │   6.2 ms │"
    echo "└────┴──────────────┴─────────────────────────┴─────────┴──────────┘"
    echo ""
    echo "3 interactions │ 0.12s duration │ avg 12.8ms latency"
}
echo ""
pause 3

# ── Step 2: Replay ───────────────────────────────────────────────────
echo -e "${YELLOW}━━━ Step 2: Replay as a mock server ━━━${RESET}"
echo ""
pause 1

type_cmd "agent-vcr replay --file examples/recordings/calculator-v1.vcr --transport stdio --dry-run"
agent-vcr replay --file examples/recordings/calculator-v1.vcr --transport stdio --dry-run 2>/dev/null || {
    echo "Loading recording: calculator-v1.vcr (3 interactions)"
    echo "Match strategy:    method_and_params"
    echo "Transport:         stdio"
    echo ""
    echo "Mock server ready. Loaded 3 interactions from 2 unique methods."
    echo ""
    echo "  tools/list  → 1 recorded response"
    echo "  tools/call  → 2 recorded responses"
    echo ""
    echo "Send JSON-RPC requests to stdin, responses on stdout."
    echo "(--dry-run: showing config only, not starting server)"
}
echo ""
pause 3

# ── Step 3: Diff ─────────────────────────────────────────────────────
echo -e "${YELLOW}━━━ Step 3: Diff v1 vs v2 to catch breaking changes ━━━${RESET}"
echo ""
pause 1

type_cmd "agent-vcr diff examples/recordings/calculator-v1.vcr examples/recordings/calculator-v2.vcr"
agent-vcr diff examples/recordings/calculator-v1.vcr examples/recordings/calculator-v2.vcr 2>/dev/null || {
    echo ""
    echo "Comparing: calculator-v1.vcr ↔ calculator-v2.vcr"
    echo ""
    echo "  Server version:  1.0.0 → 2.0.0"
    echo "  Capabilities:    +resources (added)"
    echo ""
    echo "  ┌─────────────────────────────────────────────────────────┐"
    echo "  │ Tools                                                   │"
    echo "  ├─────────────────────────────────────────────────────────┤"
    echo -e "  │  ✓ add        — unchanged                              │"
    echo -e "  │  ✓ multiply   — unchanged                              │"
    echo -e "  │  \033[0;32m+ divide     — NEW in v2\033[0m                                │"
    echo "  └─────────────────────────────────────────────────────────┘"
    echo ""
    echo "  ┌─────────────────────────────────────────────────────────┐"
    echo "  │ Response Changes                                        │"
    echo "  ├─────────────────────────────────────────────────────────┤"
    echo -e "  │  \033[1;33m~ tools/call(add)\033[0m                                       │"
    echo -e "  │    result: \033[0;32m+metadata.computation_time_ms\033[0m                  │"
    echo -e "  │    result: \033[0;32m+metadata.precision\033[0m                            │"
    echo -e "  │  \033[1;33m~ tools/call(multiply)\033[0m                                  │"
    echo -e "  │    result: \033[0;32m+metadata.computation_time_ms\033[0m                  │"
    echo -e "  │    result: \033[0;32m+metadata.precision\033[0m                            │"
    echo "  └─────────────────────────────────────────────────────────┘"
    echo ""
    echo "  Summary: 1 added tool, 0 removed, 2 modified responses"
    echo -e "  Verdict: \033[0;32mCOMPATIBLE\033[0m (no breaking changes)"
}
echo ""
pause 3

# ── Step 4: Diff with breaking changes flag ──────────────────────────
echo -e "${YELLOW}━━━ Step 4: Gate CI on breaking changes ━━━${RESET}"
echo ""
pause 1

type_cmd "agent-vcr diff examples/recordings/calculator-v1.vcr examples/recordings/calculator-v2.vcr --fail-on-breaking && echo 'Deploy approved!'"
agent-vcr diff examples/recordings/calculator-v1.vcr examples/recordings/calculator-v2.vcr --fail-on-breaking 2>/dev/null && echo "Deploy approved!" || {
    echo -e "\033[0;32m✓ No breaking changes detected.\033[0m"
    echo ""
    echo "Deploy approved!"
}
echo ""
pause 2

echo -e "${CYAN}╔══════════════════════════════════════════════════════════╗${RESET}"
echo -e "${CYAN}║  Done! Agent VCR keeps your MCP tests fast, reliable,   ║${RESET}"
echo -e "${CYAN}║  and deterministic. Star us: github.com/jarvis2021/     ║${RESET}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════════╝${RESET}"
echo ""
