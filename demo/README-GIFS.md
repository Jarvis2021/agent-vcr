# Creating GIFs for All 12 Labs

This guide explains how to record terminal sessions for each of the [tutorial](../docs/tutorial.md) labs and convert them to GIFs (e.g. for docs or README).

## Prerequisites

1. **asciinema** — record terminal sessions to `.cast` files  
   - macOS: `brew install asciinema`  
   - Or: `pip install asciinema`

2. **agg** — convert `.cast` to GIF (official asciinema tool)  
   - [agg on GitHub](https://github.com/asciinema/agg)  
   - macOS: `brew install agg` (or install from [releases](https://github.com/asciinema/agg/releases))  
   - Or use [asciinema’s agg docs](https://docs.asciinema.org/manual/agg/) for other platforms

3. **Agent VCR** — install the Python CLI from the repo root:
   ```bash
   cd agent-vcr/python && uv pip install -e . && cd ../..
   ```
   Ensure `agent-vcr` is on your `PATH` (or run from `python/` with `python -m agent_vcr.cli`).

## Quick: One lab → GIF

From the **repository root**:

```bash
# Record Lab N (1–12) into a .cast file
asciinema rec demo/lab-N.cast -c "bash demo/make-lab-gifs.sh N"

# Convert to GIF
agg demo/lab-N.cast demo/lab-N.gif
```

Example for Lab 3 (diff):

```bash
asciinema rec demo/lab-3.cast -c "bash demo/make-lab-gifs.sh 3"
agg demo/lab-3.cast demo/lab-3.gif
```

## All 12 labs

| Lab | Topic | Script runs |
|-----|--------|-------------|
| 1 | Your first recording | Record with `--demo`, then inspect |
| 2 | Replaying | Replay + dry-run; pipe one request to replayer |
| 3 | Diffing | Diff calculator v1 vs v2 |
| 4 | Golden cassette | Create cassette dir, record with `--demo`, run pytest (if test exists) |
| 5 | Compatibility gates | Record v1/v2, diff with `--fail-on-breaking` |
| 6 | Error injection | Inspect error recording; run error-injection test (if exists) |
| 7 | Offline dev | Record then replay (stdio) |
| 8 | Multi-agent | Create team dirs, record baselines, diff |
| 9 | Protocol evolution | Run diff on example recordings |
| 10 | Programmatic recording | Run create_sample_recording example |
| 11 | Pytest integration | Run a single pytest with VCR marker (if test exists) |
| 12 | asciinema demo | Run existing record-demo.sh |

Run each with:

```bash
asciinema rec demo/lab-1.cast -c "bash demo/make-lab-gifs.sh 1"
# ... same for 2–12
agg demo/lab-1.cast demo/lab-1.gif
# ...
```

## Batch: record all 12 labs

```bash
for n in $(seq 1 12); do
  asciinema rec "demo/lab-${n}.cast" -c "bash demo/make-lab-gifs.sh $n"
done
```

Then convert all to GIF:

```bash
for n in $(seq 1 12); do
  agg "demo/lab-${n}.cast" "demo/lab-${n}.gif"
done
```

## GIF options (agg)

- **Speed:** `agg --speed 2 demo/lab-1.cast demo/lab-1.gif` (2× playback)
- **Theme:** `agg --theme monokai demo/lab-1.cast demo/lab-1.gif`
- **Font size:** `agg --font-size 16 demo/lab-1.cast demo/lab-1.gif`

See `agg --help` and [agg usage](https://docs.asciinema.org/manual/agg/usage).

## Files

- **make-lab-gifs.sh** — accepts lab number 1–12, runs that lab’s commands (non-interactive where possible).
- **record-demo.sh** — single walkthrough (inspect, replay dry-run, diff, fail-on-breaking); used for the main README demo and Lab 12.

The main repo demo GIF (`assets/demo.gif`) is typically made from `record-demo.sh`, not from the per-lab script.

---

## Correlation demo (--endpoint-id / --session-id)

To show **correlation metadata** (multi-session / multi-MCP support) without implying the full orchestrator:

```bash
# Record the demo (record with endpoint_id + session_id, then inspect)
asciinema rec demo/correlation-demo.cast -c "bash demo/record-correlation-demo.sh"

# Convert to GIF (e.g. for README or docs/scaling.md)
agg demo/correlation-demo.cast assets/correlation-demo.gif
```

The script records one session with `--endpoint-id filesystem` and `--session-id run-demo-*`, then runs `inspect` so the output shows Session ID and Endpoint ID in the metadata table.
