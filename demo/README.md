# Agent VCR Demo

Two ways to create the README demo recording:

## Option A: Upload the pre-built cast file (fastest)

The `agent-vcr-demo.cast` file is a handcrafted [asciicast v2](https://docs.asciinema.org/manual/asciicast/v2/) recording showing the full workflow. Upload it directly:

```bash
# Install asciinema
brew install asciinema          # macOS
# pip install asciinema         # or via pip

# Upload the pre-built recording
asciinema upload demo/agent-vcr-demo.cast

# It will print a URL like:
# https://asciinema.org/a/abc123
# Use that URL to update the README embed
```

## Option B: Record a live session (more authentic)

Run the demo script while asciinema records your real terminal:

```bash
# Make sure agent-vcr is installed
pip install -e ".[dev]"

# Record
asciinema rec demo/live-demo.cast -c "bash demo/record-demo.sh"

# Preview locally
asciinema play demo/live-demo.cast

# Upload
asciinema upload demo/live-demo.cast
```

## After uploading

1. Copy the URL from asciinema (e.g., `https://asciinema.org/a/abc123`)
2. Update the README.md embed:
   ```markdown
   [![Agent VCR Demo](https://asciinema.org/a/abc123.svg)](https://asciinema.org/a/abc123)
   ```

## Sample recordings

The `examples/recordings/` directory contains `.vcr` cassette files you can use to test the CLI:

- `calculator-v1.vcr` — Basic calculator MCP session (3 interactions)
- `calculator-v2.vcr` — Updated version with new tool + metadata (4 interactions)
- `calculator-errors.vcr` — Session with error responses (division by zero, method not found)

```bash
agent-vcr inspect examples/recordings/calculator-v1.vcr
agent-vcr diff examples/recordings/calculator-v1.vcr examples/recordings/calculator-v2.vcr
```
