# Changelog

## [0.8.1] - 2026-01-19

### Fixed
- Bug 1: Claude runner configuration (removed incompatible flags)
- Bug 2: Exit logic infinite loop (added all_blocked() detection)
- Bug 3: YAML tracker status counting (no longer counts blocked as done)

### Technical Details
- Added `all_blocked()` method to Tracker protocol
- Updated loop exit logic to distinguish all_done vs all_blocked
- Fixed YAML tracker counts to be accurate
