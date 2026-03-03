#!/usr/bin/env node
/**
 * Setup script for simple-git-hooks
 *
 * Run this script after 'harness init' to wire pre-commit hooks into package.json:
 *   node scripts/setup-git-hooks.js
 *
 * This script:
 *   1. Adds simple-git-hooks to devDependencies (if not present)
 *   2. Adds postinstall script to run simple-git-hooks
 *   3. Adds simple-git-hooks configuration
 *   4. Runs pnpm install to activate hooks
 */

import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { execFileSync } from "node:child_process";

const PACKAGE_JSON_PATH = resolve(process.cwd(), "package.json");

function main() {
	if (!existsSync(PACKAGE_JSON_PATH)) {
		console.error("Error: package.json not found in current directory");
		console.error("  Run this script from your project root.");
		process.exit(1);
	}

	let packageJson: Record<string, unknown>;
	try {
		packageJson = JSON.parse(readFileSync(PACKAGE_JSON_PATH, "utf-8"));
	} catch {
		console.error("Error: Failed to parse package.json");
		process.exit(1);
	}

	let modified = false;

	// Ensure devDependencies exists
	if (!packageJson.devDependencies) {
		packageJson.devDependencies = {};
	}

	// Add simple-git-hooks if not present
	const deps = packageJson.devDependencies as Record<string, string>;
	if (!deps["simple-git-hooks"]) {
		deps["simple-git-hooks"] = "^2.13.1";
		console.info("✓ Added simple-git-hooks to devDependencies");
		modified = true;
	} else {
		console.info("✓ simple-git-hooks already in devDependencies");
	}

	// Ensure scripts exists
	if (!packageJson.scripts) {
		packageJson.scripts = {};
	}

	// Add postinstall script if not present
	const scripts = packageJson.scripts as Record<string, string>;
	if (!scripts.postinstall) {
		scripts.postinstall = "simple-git-hooks";
		console.info("✓ Added postinstall script");
		modified = true;
	} else if (!scripts.postinstall.includes("simple-git-hooks")) {
		// Prepend simple-git-hooks to existing postinstall
		scripts.postinstall = `simple-git-hooks && ${scripts.postinstall}`;
		console.info("✓ Prepended simple-git-hooks to postinstall");
		modified = true;
	}

	// Add simple-git-hooks configuration
	if (!packageJson["simple-git-hooks"]) {
		packageJson["simple-git-hooks"] = {
			"pre-commit": "pnpm lint && pnpm typecheck",
			"commit-msg": "node scripts/validate-commit-msg.js $1",
			"pre-push": "pnpm test",
		};
		console.info("✓ Added simple-git-hooks configuration");
		modified = true;
	} else {
		console.info("✓ simple-git-hooks configuration already exists");
	}

	// Write changes if modified
	if (modified) {
		writeFileSync(PACKAGE_JSON_PATH, JSON.stringify(packageJson, null, 2) + "\n");
		console.info("\n✓ package.json updated");
	}

	// Run pnpm install to activate hooks (using execFileSync for safety)
	console.info("\nInstalling dependencies to activate hooks...");
	try {
		execFileSync("pnpm", ["install"], { stdio: "inherit" });
		console.info("\n✓ Git hooks installed and active!");
		console.info("\nHooks enabled:");
		console.info("  • pre-commit: pnpm lint && pnpm typecheck");
		console.info("  • commit-msg: validates conventional commit format");
		console.info("  • pre-push: pnpm test");
	} catch {
		console.error("\n⚠️  Failed to run pnpm install. Run it manually to activate hooks.");
	}
}

main();
