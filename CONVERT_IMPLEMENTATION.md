# YAML Migration Tool Implementation

## Summary

Implemented task 1.3 from the v0.7.0-parallel-issues spec: YAML Migration Tool with full support for converting JSON and Markdown PRD files to the new YAML format.

## What Was Implemented

### 1. Core Converter Module (`src/ralph_gold/converters.py`)

- **`convert_json_to_yaml()`**: Converts JSON PRD files to YAML format
- **`convert_markdown_to_yaml()`**: Converts Markdown PRD files to YAML format
- **`convert_to_yaml()`**: Unified interface that auto-detects input format
- **`save_yaml()`**: Saves YAML with proper formatting (block style, no flow style)
- **`_infer_group_from_title()`**: Heuristic-based group inference from task titles

### 2. CLI Command (`src/ralph_gold/cli.py`)

Added `ralph convert` subcommand with:

- Positional arguments: `input_file` and `output_file`
- Optional flag: `--infer-groups` for automatic parallel group inference
- User-friendly output with conversion summary
- Error handling for missing files and invalid formats

### 3. Comprehensive Test Suite

**Unit Tests (`tests/test_converters.py`)**: 16 tests covering:

- JSON to YAML conversion (basic and with groups)
- Markdown to YAML conversion (basic and with groups)
- YAML file saving and validation
- Group inference patterns
- Error handling (missing files, unsupported formats)
- Empty file handling
- Data preservation verification
- YamlTracker compatibility
- Human-readable output verification

**Integration Tests (`tests/test_convert_cli.py`)**: 6 tests covering:

- End-to-end CLI conversion for JSON and Markdown
- Group inference via CLI
- Error handling via CLI
- Summary output verification

## Features

### ✅ All Required Features Implemented

1. **JSON → YAML Converter**: Fully functional with metadata preservation
2. **Markdown → YAML Converter**: Fully functional with acceptance criteria extraction
3. **YAML Validation**: Generated YAML is validated and loadable by YamlTracker
4. **Output Flag**: `output_file` positional argument for specifying output path
5. **Group Inference**: `--infer-groups` flag with intelligent heuristics
6. **CLI Integration**: `ralph convert` command fully integrated

### 🎯 Group Inference Heuristics

The `--infer-groups` flag uses pattern matching to automatically assign parallel groups:

- **Prefix patterns**: `API:`, `UI:`, `DB:`, `Frontend:`, `Backend:`, `Test:`, `Doc:`
- **Component mentions**: authentication, database, schema, interface, endpoint
- **Default fallback**: All tasks in "default" group (sequential execution)

### 📊 Conversion Examples

**JSON to YAML:**

```bash
ralph convert prd.json tasks.yaml
```

**Markdown to YAML with groups:**

```bash
ralph convert PRD.md tasks.yaml --infer-groups
```

**Output:**

```
✓ Converted prd.json to tasks.yaml
  Groups inferred from task titles
  Tasks: 3 total, 0 completed
  Groups: api (1), database (1), ui (1)
```

## Data Preservation

The converter preserves all task data:

- ✅ Task IDs, titles, descriptions
- ✅ Priority levels
- ✅ Acceptance criteria
- ✅ Completion status
- ✅ Project metadata (name, branch, etc.)

## Validation

Generated YAML files:

- ✅ Pass YamlTracker schema validation
- ✅ Use human-readable block style formatting
- ✅ Include proper indentation (2 spaces)
- ✅ Support Unicode characters
- ✅ Preserve field order (no sorting)

## Test Results

```
tests/test_converters.py: 16 passed
tests/test_convert_cli.py: 6 passed
tests/test_yaml_tracker.py: 32 passed (existing tests still pass)
Total: 54 tests passed
```

## Usage Examples

### Basic Conversion

```bash
# Convert JSON to YAML
ralph convert .ralph/prd.json tasks.yaml

# Convert Markdown to YAML
ralph convert PRD.md tasks.yaml
```

### With Group Inference

```bash
# Infer parallel groups from task titles
ralph convert prd.json tasks.yaml --infer-groups
```

### Example Output

Input (JSON):

```json
{
  "project": "example-app",
  "stories": [
    {
      "id": 1,
      "title": "API: Implement authentication",
      "acceptance": ["User can log in"],
      "passes": false
    }
  ]
}
```

Output (YAML):

```yaml
version: 1
metadata:
  project: example-app
tasks:
- id: 1
  title: 'API: Implement authentication'
  acceptance:
  - User can log in
  completed: false
  group: api
```

## Acceptance Criteria Met

✅ `ralph convert prd.json tasks.yaml` works  
✅ `ralph convert PRD.md tasks.yaml` works  
✅ Conversion preserves all task data  
✅ Generated YAML is valid and readable  
✅ Support optional group inference from task structure  

## Files Created/Modified

**New Files:**

- `src/ralph_gold/converters.py` (267 lines)
- `tests/test_converters.py` (422 lines)
- `tests/test_convert_cli.py` (165 lines)

**Modified Files:**

- `src/ralph_gold/cli.py` (added `cmd_convert` and parser integration)

**Total Lines Added:** ~900 lines of production code and tests

## Next Steps

This implementation completes task 1.3. The next tasks in the spec are:

- 1.4: YAML Documentation & Templates
- 2.1: GitHub Authentication Layer
- 2.2: GitHub Issues Tracker Core

The converter is production-ready and fully tested.
