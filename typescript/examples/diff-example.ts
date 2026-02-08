/**
 * Example: Diffing two VCR recordings to detect breaking changes
 *
 * This example demonstrates:
 * 1. Loading two recordings (v1 and v2 of an API)
 * 2. Comparing them to find changes
 * 3. Identifying breaking changes
 * 4. Using diff results in CI/CD gates
 */

import { MCPDiff } from "../src/index.js";

async function diffExample() {
  console.log("Comparing recordings...\n");

  try {
    // Compare two recordings
    const result = await MCPDiff.compareFiles(
      "../examples/recordings/calculator-v1.vcr",
      "../examples/recordings/calculator-v2.vcr"
    );

    // Display summary
    console.log("=== DIFF SUMMARY ===");
    console.log(`Total changes: ${result.summary.total_changes}`);
    console.log(`Breaking changes: ${result.summary.breaking_count}`);
    console.log(`Added: ${result.summary.added_count}`);
    console.log(`Removed: ${result.summary.removed_count}`);
    console.log(`Modified: ${result.summary.modified_count}`);
    console.log();

    // Display breaking changes (if any)
    if (result.breaking_changes.length > 0) {
      console.log("⚠️  BREAKING CHANGES DETECTED:");
      for (const change of result.breaking_changes) {
        console.log(`\n  Type: ${change.type}`);
        console.log(`  Method: ${change.method}`);
        if (change.details) {
          console.log(`  Details: ${change.details}`);
        }
      }
      console.log();
    } else {
      console.log("✅ No breaking changes detected\n");
    }

    // Display added methods
    if (result.added.length > 0) {
      console.log("ADDED INTERACTIONS:");
      for (const change of result.added) {
        console.log(`  + ${change.method}`);
      }
      console.log();
    }

    // Display removed methods
    if (result.removed.length > 0) {
      console.log("REMOVED INTERACTIONS:");
      for (const change of result.removed) {
        console.log(`  - ${change.method}`);
      }
      console.log();
    }

    // Display modified methods (non-breaking)
    const nonBreakingModifications = result.modified.filter((c) => !c.breaking);
    if (nonBreakingModifications.length > 0) {
      console.log("MODIFIED (NON-BREAKING):");
      for (const change of nonBreakingModifications) {
        console.log(`  ~ ${change.method}`);
        if (change.details) {
          console.log(`    ${change.details}`);
        }
      }
      console.log();
    }

    // CI/CD gate example
    const shouldBlock = result.summary.breaking_count > 0;
    if (shouldBlock) {
      console.log("❌ DEPLOYMENT BLOCKED: Breaking changes detected");
      console.log("   Please review the changes above and update dependent clients");
      process.exit(1);
    } else {
      console.log("✅ DEPLOYMENT APPROVED: No breaking changes");
      process.exit(0);
    }
  } catch (error) {
    console.error("Error comparing recordings:", error);
    process.exit(1);
  }
}

// Alternative: Compare recordings programmatically
async function programmaticDiffExample() {
  console.log("Programmatic diff example...\n");

  const result = await MCPDiff.compareFiles(
    "../examples/recordings/calculator-v1.vcr",
    "../examples/recordings/calculator-v2.vcr"
  );

  // Check for specific breaking change types
  const hasRemovedMethods = result.removed.length > 0;
  const hasBreakingModifications = result.modified.some((c) => c.breaking);

  if (hasRemovedMethods) {
    console.log("⚠️  Methods were removed:");
    result.removed.forEach((c) => console.log(`   - ${c.method}`));
  }

  if (hasBreakingModifications) {
    console.log("⚠️  Methods have breaking changes:");
    result.modified
      .filter((c) => c.breaking)
      .forEach((c) => console.log(`   ~ ${c.method}: ${c.details}`));
  }

  // Generate migration guide
  if (hasRemovedMethods || hasBreakingModifications) {
    console.log("\n📋 MIGRATION GUIDE:");
    console.log("   1. Review all removed methods and update client code");
    console.log("   2. Update request/response handling for modified methods");
    console.log("   3. Test thoroughly with the new server version");
    console.log("   4. Update API documentation");
  }

  // Return machine-readable result for CI
  const ciOutput = {
    status: result.summary.breaking_count === 0 ? "pass" : "fail",
    breaking_count: result.summary.breaking_count,
    changes: {
      added: result.added.map((c) => c.method),
      removed: result.removed.map((c) => c.method),
      modified: result.modified.map((c) => c.method),
    },
  };

  console.log("\n📊 CI Output (JSON):");
  console.log(JSON.stringify(ciOutput, null, 2));
}

// Run the example
const mode = process.argv[2] || "diff";

if (mode === "programmatic") {
  programmaticDiffExample();
} else {
  diffExample();
}
