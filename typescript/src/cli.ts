#!/usr/bin/env node

/**
 * Agent VCR CLI
 *
 * Command-line interface for recording, replaying, and diffing MCP interactions.
 */

import { Command } from "commander";
import { promises as fs } from "fs";
import chalk from "chalk";
import { MCPRecorder } from "./recorder.js";
import { MCPReplayer } from "./replayer.js";
import { MCPDiff } from "./diff.js";
import { MatchStrategy } from "./core/matcher.js";

const program = new Command();

program
  .name("agent-vcr")
  .description("Record, replay, and diff MCP interactions")
  .version("0.1.0");

// Record command
program
  .command("record")
  .description("Record MCP interactions to a .vcr file")
  .requiredOption("--transport <type>", "Transport type: stdio or sse")
  .requiredOption("--server-command <cmd>", "Command to start the MCP server")
  .option("--server-args <args...>", "Arguments for the server command")
  .option("--host <host>", "Host for SSE transport", "127.0.0.1")
  .option("--port <port>", "Port for SSE transport", "3000")
  .option("-o, --output <path>", "Output .vcr file path", "recording.vcr")
  .option("--tag <key=value...>", "Add custom tags to the recording")
  .action(async (options) => {
    try {
      console.log(chalk.blue("Starting MCP recorder..."));

      const tags: Record<string, string> = {};
      if (options.tag) {
        for (const tag of options.tag) {
          const [key, value] = tag.split("=");
          if (key && value) {
            tags[key] = value;
          }
        }
      }

      const recorder = new MCPRecorder({
        transport: options.transport as "stdio" | "sse",
        command: options.serverCommand,
        args: options.serverArgs,
        host: options.host,
        port: parseInt(options.port, 10),
        metadata: { tags },
      });

      await recorder.start();

      console.log(chalk.green("Recording started. Press Ctrl+C to stop."));

      // Handle graceful shutdown
      const shutdown = async () => {
        console.log(chalk.yellow("\nStopping recording..."));
        const recording = await recorder.stop();
        await recorder.save(recording, options.output);
        console.log(chalk.green(`Recording saved to ${options.output}`));
        process.exit(0);
      };

      process.on("SIGINT", shutdown);
      process.on("SIGTERM", shutdown);

      // Keep process alive
      await new Promise(() => {});
    } catch (error) {
      console.error(chalk.red("Error:"), error);
      process.exit(1);
    }
  });

// Replay command
program
  .command("replay")
  .description("Replay a .vcr recording as a mock MCP server")
  .requiredOption("-i, --input <path>", "Input .vcr file path")
  .option("--transport <type>", "Transport type: stdio or sse", "stdio")
  .option("--host <host>", "Host for SSE transport", "127.0.0.1")
  .option("--port <port>", "Port for SSE transport", "3000")
  .option(
    "--match <strategy>",
    "Match strategy: exact, method, method_and_params, fuzzy, sequential",
    "method_and_params"
  )
  .option("--strict", "Fail on unmatched requests", false)
  .action(async (options) => {
    try {
      console.log(chalk.blue("Loading recording..."));

      const replayer = await MCPReplayer.fromFile(
        options.input,
        options.match as MatchStrategy,
        options.strict
      );

      console.log(chalk.green("Recording loaded successfully"));

      if (options.transport === "stdio") {
        console.log(chalk.blue("Starting stdio replayer..."));
        await replayer.serveStdio();
      } else if (options.transport === "sse") {
        console.log(
          chalk.blue(`Starting SSE replayer on ${options.host}:${options.port}...`)
        );
        await replayer.serveSSE(options.host, parseInt(options.port, 10));
      } else {
        throw new Error(`Unknown transport: ${options.transport}`);
      }
    } catch (error) {
      console.error(chalk.red("Error:"), error);
      process.exit(1);
    }
  });

// Diff command
program
  .command("diff")
  .description("Compare two .vcr recordings and detect changes")
  .requiredOption("-b, --baseline <path>", "Baseline .vcr file")
  .requiredOption("-c, --current <path>", "Current .vcr file")
  .option("--fail-on-breaking", "Exit with code 1 if breaking changes detected", false)
  .option("--json", "Output as JSON", false)
  .action(async (options) => {
    try {
      console.log(chalk.blue("Comparing recordings..."));

      const result = await MCPDiff.compareFiles(options.baseline, options.current);

      if (options.json) {
        console.log(JSON.stringify(result, null, 2));
      } else {
        // Pretty print the diff
        console.log(chalk.bold("\n=== Summary ==="));
        console.log(`Total changes: ${result.summary.total_changes}`);
        console.log(
          chalk.red(`Breaking changes: ${result.summary.breaking_count}`)
        );
        console.log(chalk.green(`Added: ${result.summary.added_count}`));
        console.log(chalk.red(`Removed: ${result.summary.removed_count}`));
        console.log(chalk.yellow(`Modified: ${result.summary.modified_count}`));

        if (result.breaking_changes.length > 0) {
          console.log(chalk.bold.red("\n=== Breaking Changes ==="));
          for (const change of result.breaking_changes) {
            console.log(`\n${chalk.red("✗")} ${change.type}: ${change.method}`);
            if (change.details) {
              console.log(`  ${change.details}`);
            }
          }
        }

        if (result.added.length > 0) {
          console.log(chalk.bold.green("\n=== Added ==="));
          for (const change of result.added) {
            console.log(`${chalk.green("+")} ${change.method}`);
          }
        }

        if (result.removed.length > 0) {
          console.log(chalk.bold.red("\n=== Removed ==="));
          for (const change of result.removed) {
            console.log(`${chalk.red("-")} ${change.method}`);
          }
        }

        if (result.modified.length > 0 && result.modified.length <= 10) {
          console.log(chalk.bold.yellow("\n=== Modified ==="));
          for (const change of result.modified) {
            if (!change.breaking) {
              console.log(`${chalk.yellow("~")} ${change.method}`);
              if (change.details) {
                console.log(`  ${change.details}`);
              }
            }
          }
        }
      }

      if (options.failOnBreaking && result.summary.breaking_count > 0) {
        console.log(
          chalk.red(`\nFailing due to ${result.summary.breaking_count} breaking changes`)
        );
        process.exit(1);
      }
    } catch (error) {
      console.error(chalk.red("Error:"), error);
      process.exit(1);
    }
  });

// Inspect command
program
  .command("inspect")
  .description("Inspect a .vcr recording and display metadata")
  .requiredOption("-i, --input <path>", "Input .vcr file path")
  .option("--json", "Output as JSON", false)
  .action(async (options) => {
    try {
      const content = await fs.readFile(options.input, "utf-8");
      const recording = JSON.parse(content);

      if (options.json) {
        console.log(JSON.stringify(recording, null, 2));
      } else {
        console.log(chalk.bold("=== Recording Metadata ==="));
        console.log(`Format version: ${recording.format_version}`);
        console.log(`Recorded at: ${recording.metadata.recorded_at}`);
        console.log(`Transport: ${recording.metadata.transport}`);
        console.log(
          `Server: ${recording.metadata.server_info?.name || "unknown"} ${recording.metadata.server_info?.version || ""}`
        );
        console.log(
          `Client: ${recording.metadata.client_info?.name || "unknown"} ${recording.metadata.client_info?.version || ""}`
        );
        console.log(`Interactions: ${recording.session.interactions.length}`);

        if (Object.keys(recording.metadata.tags || {}).length > 0) {
          console.log(chalk.bold("\n=== Tags ==="));
          for (const [key, value] of Object.entries(recording.metadata.tags)) {
            console.log(`${key}: ${value}`);
          }
        }

        console.log(chalk.bold("\n=== Interactions ==="));
        const methods = new Map<string, number>();
        for (const interaction of recording.session.interactions) {
          const method = interaction.request.method;
          methods.set(method, (methods.get(method) || 0) + 1);
        }

        for (const [method, count] of methods.entries()) {
          console.log(`${method}: ${count}`);
        }
      }
    } catch (error) {
      console.error(chalk.red("Error:"), error);
      process.exit(1);
    }
  });

// Convert command (for future compatibility)
program
  .command("convert")
  .description("Convert between .vcr format versions")
  .requiredOption("-i, --input <path>", "Input .vcr file")
  .requiredOption("-o, --output <path>", "Output .vcr file")
  .option("--to-version <version>", "Target format version", "1.0.0")
  .action(async (options) => {
    try {
      console.log(chalk.blue("Converting recording..."));

      // For now, just validate and re-save
      const content = await fs.readFile(options.input, "utf-8");
      const recording = JSON.parse(content);

      recording.format_version = options.toVersion;

      await fs.writeFile(options.output, JSON.stringify(recording, null, 2));

      console.log(chalk.green(`Converted recording saved to ${options.output}`));
    } catch (error) {
      console.error(chalk.red("Error:"), error);
      process.exit(1);
    }
  });

program.parse();
