---
last_validated: 2026-02-28
---

# Ralph Init Archiving

## Overview

`ralph init` now automatically archives existing `.ralph` files when using the `--force` flag, preventing accidental data loss during re-initialization.

## Behavior

### Without `--force` (default)

```bash
ralph init
```

- Skips any files that already exist
- Preserves your existing work
- Only creates missing files

### With `--force`

```bash
ralph init --force
```

- **Automatically archives** existing files to `.ralph/archive/<timestamp>/`
- Creates fresh template files
- Shows summary of archived files

## Archive Structure

Archives are organized by timestamp:

```
.ralph/
├── archive/
│   ├── 20260118-143022/
│   │   ├── .ralph/
│   │   │   ├── prd.json
│   │   │   ├── PROMPT.md
│   │   │   └── ...
│   │   └── tasks.yaml (if root-level)
│   └── 20260118-150315/
│       └── .ralph/
│           └── ...
├── prd.json (fresh template)
└── ...
```

## Example Output

```bash
$ ralph init --force

Initialized Ralph files in: /path/to/project/.ralph

✓ Archived 12 existing file(s) to .ralph/archive/
  - .ralph/prd.json
  - .ralph/PROMPT.md
  - .ralph/progress.md
  - .ralph/AGENTS.md
  - .ralph/ralph.toml
  ... and 7 more
```

## Use Cases

### Starting a New Feature Set

```bash
# Archive old work and start fresh
ralph init --force --format json
```

### Recovering Archived Files

```bash
# List archives
ls -la .ralph/archive/

# Restore specific file
cp .ralph/archive/20260118-143022/.ralph/prd.json .ralph/prd-recovered.json
```

### Comparing Old vs New

```bash
# Diff archived vs current
diff .ralph/archive/20260118-143022/.ralph/prd.json .ralph/prd.json
```

## Notes

- Archives are **excluded from git** by default (`.gitignore`)
- Each `ralph init --force` creates a **separate timestamped archive**
- Archives preserve the **original directory structure**
- Archive timestamps use UTC in format `YYYYMMDD-HHMMSS`

## Migration from Manual Backups

If you previously backed up files manually:

```bash
# Old way (manual)
cp -r .ralph .ralph.backup
ralph init --force

# New way (automatic)
ralph init --force  # Archives automatically
```

The automatic archiving is safer because:

- Consistent timestamp format
- Preserves directory structure
- Can't accidentally overwrite backups
- Easy to find and compare multiple versions
