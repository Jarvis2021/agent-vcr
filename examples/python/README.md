# Agent VCR Python Examples

This directory contains Python examples demonstrating the Agent VCR APIs for recording, replaying, and diffing MCP sessions.

## Examples

### 1. create_sample_recording.py

**Purpose:** Programmatically create a sample .vcr recording file with realistic MCP interactions.

**What it demonstrates:**
- Creating VCRRecording, VCRSession, and VCRInteraction objects
- Constructing JSON-RPC 2.0 requests and responses
- Including proper metadata (timestamps, transport, client/server info)
- Handling both success and error responses
- Saving recordings to disk with `.save()`

**Use cases:**
- Testing without a real MCP server
- Generating sample data for documentation
- Creating test fixtures for unit tests
- Understanding the VCR format structure

**Usage:**
```bash
python create_sample_recording.py [output_path]
python create_sample_recording.py sample.vcr
```

**Output:**
Creates a `.vcr` file with interactions including:
- Initialize handshake
- tools/list request
- tools/call request (calculate expression)
- resources/read request (success case)
- resources/read request (error case)

### 2. replay_recording.py

**Purpose:** Load a .vcr file and use MCPReplayer to handle requests against recorded responses.

**What it demonstrates:**
- Loading recordings with `MCPReplayer.from_file()`
- Initializing replayer with different match strategies
- Handling requests with `replayer.handle_request()`
- Using response overrides for custom scenarios
- Testing error cases with unknown requests
- Extracting request/response metadata

**Use cases:**
- Testing MCP clients against recorded sessions
- Creating mock servers for integration tests
- Replaying real-world interactions for debugging
- Validating client behavior with consistent server responses

**Usage:**
```bash
python replay_recording.py <vcr_file> [match_strategy]
python replay_recording.py sample.vcr method_and_params
python replay_recording.py sample.vcr exact
```

**Match strategies:**
- `method_and_params` (default): Match by method name and parameters
- `exact`: Match entire request exactly
- `method`: Match by method name only

**Output:**
Demonstrates 6 examples:
1. Replaying tools/list request
2. Replaying tools/call request
3. Replaying successful resources/read request
4. Replaying failed resources/read request
5. Using response overrides for custom responses
6. Handling unknown/unmapped requests

### 3. diff_recordings.py

**Purpose:** Create two slightly different recordings and diff them using MCPDiff.

**What it demonstrates:**
- Creating multiple VCRRecording objects
- Using `MCPDiff.compare()` to compare recordings
- Interpreting diff results (added, removed, modified interactions)
- Detecting breaking changes
- Checking backward compatibility
- Analyzing interaction changes in detail

**Use cases:**
- Regression testing: baseline vs. current behavior
- Detecting breaking changes in server updates
- Validating that client changes don't break compatibility
- Understanding evolution of MCP interactions over time

**Usage:**
```bash
python diff_recordings.py
```

**Output:**
Creates two recordings and shows:
- Summary of differences (added, removed, modified interactions)
- Detailed table view of changes (using Rich formatting)
- Breaking change detection
- Compatibility assessment
- Individual interaction change analysis

**Example changes demonstrated:**
- Tool list modification (removed 'fetch', added 'search')
- Response content changes
- New interactions added
- Response structure modifications

## Prerequisites

Install the Agent VCR package:

```bash
pip install agent-vcr
```

For full diff functionality (MCPDiff), ensure optional dependencies are installed:

```bash
pip install agent-vcr[diff]
```

## Running the Examples

### Quick Start

1. Create a sample recording:
```bash
python create_sample_recording.py my_recording.vcr
```

2. Replay the recording:
```bash
python replay_recording.py my_recording.vcr
```

3. Diff two recordings:
```bash
python diff_recordings.py
```

### Integration with Your Project

Each script is self-contained and can be integrated into your workflow:

**Recording generation:**
```python
from create_sample_recording import create_sample_recording
recording = create_sample_recording()
recording.save("my_recording.vcr")
```

**Replaying programmatically:**
```python
from agent_vcr.replayer import MCPReplayer
replayer = MCPReplayer.from_file("recording.vcr")
response = replayer.handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
```

**Comparing recordings:**
```python
from agent_vcr.diff import MCPDiff
diff = MCPDiff.compare("baseline.vcr", "current.vcr")
print(diff.summary())
if not diff.is_compatible:
    print("Breaking changes detected!")
```

## Key APIs

### VCRRecording
- `.save(path)` - Save recording to JSON file
- `.load(path)` - Load recording from JSON file (class method)
- `.model_validate(data)` - Create from dict (class method)
- `.add_interaction(interaction)` - Add an interaction
- `.duration` - Total session duration in seconds
- `.interaction_count` - Number of interactions

### MCPReplayer
- `MCPReplayer.from_file(path, match_strategy)` - Load from file
- `.handle_request(request_dict)` - Process a JSON-RPC request
- `.set_response_override(id, response)` - Override specific response
- `.clear_response_overrides()` - Clear all overrides

### MCPDiff
- `MCPDiff.compare(baseline, current)` - Compare two recordings
- Result has `.is_identical`, `.is_compatible`, `.breaking_changes`
- `.summary()` - Text summary
- `.print_detailed()` - Rich formatted output
- `.to_dict()` - Serialize comparison result

## File Structure

Each .vcr file contains:
- **format_version**: VCR format version (e.g., "1.0.0")
- **metadata**: Recording metadata (timestamps, transport, client/server info)
- **session**: MCP session with:
  - `initialize_request`: Initial handshake request
  - `initialize_response`: Server capabilities
  - `interactions`: List of request/response pairs

## Notes

- Examples are designed to be educational and self-contained
- No external MCP servers required for these examples
- All timestamps are in ISO 8601 format
- JSON-RPC 2.0 protocol compliance is enforced by Pydantic models
- Match strategies affect how requests are matched to recorded responses in replayer

## Further Reading

- MCP Protocol: https://spec.modelcontextprotocol.io/
- JSON-RPC 2.0 Spec: https://www.jsonrpc.org/specification
- Agent VCR Documentation: See main project README
