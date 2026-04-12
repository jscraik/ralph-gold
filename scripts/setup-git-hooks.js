#!/usr/bin/env node
/**
 * Install prek-managed git hooks for this uv-first repository.
 *
 * Run from the repo root:
 *   node scripts/setup-git-hooks.js
 *
 * This script:
 *   1. Verifies prek.toml exists
 *   2. Runs `prek install`
 *   3. Prints the canonical wrapper targets used by local governance
 */

import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { execFileSync } from "node:child_process";

const PREK_CONFIG_PATH = resolve(process.cwd(), "prek.toml");

function main() {
	if (!existsSync(PREK_CONFIG_PATH)) {
		console.error("Error: prek.toml not found in current directory");
		console.error("  Run this script from your project root.");
		process.exit(1);
	}

	try {
		console.info("Installing prek git hooks...");
		execFileSync("prek", ["install"], { stdio: "inherit" });
		console.info("\n✓ Git hooks installed and active!");
		console.info("\nInstalled git-hook entrypoints:");
		console.info("  • pre-commit: make hooks-pre-commit");
		console.info("  • pre-push: make hooks-pre-push");
		console.info("\nAvailable governance wrapper targets:");
		console.info("  • make hooks-pre-commit");
		console.info("  • make hooks-commit-msg HOOK_COMMIT_MSG=\"feat: example\"");
		console.info("  • make hooks-pre-push");
	} catch (error) {
		console.error("\n⚠️  Failed to run `prek install`.");
		if (error instanceof Error && "message" in error && error.message) {
			console.error(`   ${error.message}`);
		}
		console.error("   Ensure `prek` is installed and available on PATH, then rerun the script.");
		process.exit(1);
	}
}

main();
