# Contradictions and cleanup

## Contradictions (needs decision)
1. Global vs repo description:
   - Conflict: global guidance describes a configuration-only repo; this repo is a Python CLI product.
   - Question: Should repo-local facts always override this global description in repo docs?

2. Instruction precedence wording:
   - Conflict: one rule says higher-level overrides win; another says pause and ask when conflicts appear.
   - Question: Should conflict handling default to "ask and pause" for all non-trivial conflicts?

3. Agent naming in AI policy:
   - Conflict: policy text says "Claude must" in a Codex-centric repo workflow.
   - Question: Should this be rewritten to "Agent must" for tool-neutral governance?

## Flag for deletion
- Long motivational prose that does not change execution outcomes.
- Repeated instruction-discovery details split across multiple sections.
- Duplicate policy text that can live in linked docs.
- Tool-specific wording where a tool-neutral policy is sufficient.
