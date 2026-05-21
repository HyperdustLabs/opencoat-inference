import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { Type } from "typebox";
import { defineToolPlugin } from "openclaw/plugin-sdk/tool-plugin";

const execFileAsync = promisify(execFile);

const CommonParameters = {
  baseUrl: Type.Optional(
    Type.String({
      description: "OpenCOAT Inference sidecar URL.",
      default: "http://127.0.0.1:7888",
    }),
  ),
  agentId: Type.Optional(
    Type.String({
      description: "OpenClaw consumer agent id.",
      default: "openclaw-local",
    }),
  ),
  model: Type.Optional(
    Type.String({
      description: "Model to route through OpenCOAT Inference.",
      default: "opencoat-stub",
    }),
  ),
  providerAgentId: Type.Optional(
    Type.String({
      description: "OpenCOAT provider agent id.",
      default: "agent_opencoat_stub",
    }),
  ),
  cliCommand: Type.Optional(
    Type.String({
      description: "Command used to invoke the OpenCOAT Inference CLI.",
      default: "opencoat-inference",
    }),
  ),
  cliArgsPrefix: Type.Optional(
    Type.Array(Type.String(), {
      description: "Optional arguments before the OpenCOAT CLI command, for example ['run'].",
    }),
  ),
};

type CommonInput = {
  baseUrl?: string;
  agentId?: string;
  model?: string;
  providerAgentId?: string;
  cliCommand?: string;
  cliArgsPrefix?: string[];
};

type CliResult = {
  stdout: string;
  stderr: string;
  json?: unknown;
};

function commonArgs(input: CommonInput): string[] {
  const args = [
    "--base-url",
    input.baseUrl ?? "http://127.0.0.1:7888",
    "--agent-id",
    input.agentId ?? "openclaw-local",
    "--model",
    input.model ?? "opencoat-stub",
    "--provider-agent-id",
    input.providerAgentId ?? "agent_opencoat_stub",
  ];
  return args;
}

async function runCli(input: CommonInput, args: string[]): Promise<CliResult> {
  const cliCommand = input.cliCommand ?? process.env.OPENCOAT_INFERENCE_CLI ?? "opencoat-inference";
  const cliArgsPrefix = input.cliArgsPrefix ?? parsePrefix(process.env.OPENCOAT_INFERENCE_CLI_ARGS);
  const { stdout, stderr } = await execFileAsync(
    cliCommand,
    [...cliArgsPrefix, "openclaw", ...args],
    {
      timeout: 120_000,
      maxBuffer: 1024 * 1024 * 4,
    },
  );
  return parseCliResult(stdout, stderr);
}

function parsePrefix(value: string | undefined): string[] {
  return value ? value.split(" ").filter(Boolean) : [];
}

function parseCliResult(stdout: string, stderr: string): CliResult {
  const trimmed = stdout.trim();
  if (!trimmed) {
    return { stdout, stderr };
  }
  try {
    return { stdout, stderr, json: JSON.parse(trimmed) };
  } catch {
    return { stdout, stderr };
  }
}

export default defineToolPlugin({
  id: "opencoat-inference",
  name: "OpenCOAT Inference",
  description: "Automate OpenClaw provider setup for the local OpenCOAT Inference sidecar.",
  tools: (tool) => [
    tool({
      name: "opencoat_inference_provider_config",
      description: "Return the OpenAI-compatible model config OpenClaw should use.",
      parameters: Type.Object(CommonParameters),
      execute: async (input: CommonInput) => runCli(input, ["config", ...commonArgs(input)]),
    }),
    tool({
      name: "opencoat_inference_status",
      description: "Check sidecar, wallet, balance, provider, and routing readiness.",
      parameters: Type.Object(CommonParameters),
      execute: async (input: CommonInput) => runCli(input, ["status", ...commonArgs(input)]),
    }),
    tool({
      name: "opencoat_inference_bootstrap",
      description: "Install provider and consumer wallets, grant trial credit, and return routing config.",
      parameters: Type.Object({
        ...CommonParameters,
        installWallets: Type.Optional(
          Type.Boolean({
            description: "Attempt idempotent Privy provider and consumer wallet installation.",
            default: true,
          }),
        ),
        grantTrial: Type.Optional(
          Type.Boolean({
            description: "Grant local ledger trial credit for the OpenClaw consumer agent.",
            default: true,
          }),
        ),
      }),
      execute: async (input: CommonInput & { installWallets?: boolean; grantTrial?: boolean }) => {
        const args = ["bootstrap", ...commonArgs(input)];
        args.push(input.installWallets === false ? "--no-install-wallets" : "--install-wallets");
        args.push(input.grantTrial === false ? "--no-grant-trial" : "--grant-trial");
        return runCli(input, args);
      },
    }),
    tool({
      name: "opencoat_inference_smoke_test",
      description: "Send one OpenAI-compatible request through the sidecar for this OpenClaw agent.",
      parameters: Type.Object({
        ...CommonParameters,
        input: Type.Optional(
          Type.String({
            description: "Prompt to send through OpenCOAT Inference.",
            default: "OpenClaw provider adapter smoke test",
          }),
        ),
      }),
      execute: async (input: CommonInput & { input?: string }) =>
        runCli(input, [
          "smoke-test",
          ...commonArgs(input),
          "--input",
          input.input ?? "OpenClaw provider adapter smoke test",
        ]),
    }),
  ],
});
