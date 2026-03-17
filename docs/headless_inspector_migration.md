# Headless Inspector Migration Boundary

## Objective
Decouple the file system scanning logic from the Tkinter GUI to create a reusable, stateless, and deterministic headless backend.

## Constraints & Invariants
- **No Tkinter in Core**: The reusable backend modules MUST NOT import `tkinter` or `ttk`.
- **JSON Boundary**: The primary communication contract between the backend and any host (GUI, CLI, or foreign process) is structured JSON.
- **Stateless Execution**: Each scan request is independent. The backend does not maintain session state between CLI invocations.
- **Read-Only Backend**: The core inspection logic is restricted to discovery and metadata retrieval. Mutations (Rename, Delete, ZIP) and Shell operations (Open Terminal) are responsibilities of the Host Application.
- **Formatting Independence**: The backend returns raw data (Bytes, Unix Epochs). Human-readable formatting (KB/MB, Date strings) belongs to the presentation layer.

## Architecture
## Host Integration Contract

### CLI Invocation
```powershell
python headless_inspector.py "/absolute/path" --max-depth 2 --sort-by name
```

### Standard Output (JSON)
- **Success**: Returns a JSON array of `FileNodeJSON` objects.
- **Failures**: Returns a single JSON object with `status: "error"`.

### Exit Codes
- `0`: Success.
- `1`: Validation error or IO failure.

### JSON Schema (Node)
```json
{
  "path_absolute": "string",
  "name": "string",
  "is_dir": "boolean",
  "size_bytes": "number",
  "modified_epoch_s": "number",
  "extension": "string",
  "depth": "number",
  "error": "string | null"
}
```

### Error Response Schema
```json
{
  "status": "error",
  "error_code": "PATH_NOT_FOUND | ACCESS_DENIED | INVALID_INPUT | INVALID_TARGET | IO_ERROR",
  "message": "string",
  "path": "string | null"
}
```

## Implementation Progress
- [x] Phase 0-5: Core Headless CLI functionality.
- [x] Phase 6-7: Deterministic testing and schema validation.
- [x] Phase 8: Strict static typing audit.
- [ ] Phase 9-11: Legacy cleanup (Optional/Staged).
