import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import { spawn } from "node:child_process";
import * as path from "node:path";
import * as fs from "node:fs/promises";
import { fileURLToPath } from "node:url";

// ============================================================
// Types
// ============================================================

type CLIStatus = "all_passed" | "needs_review" | "error";
type MCPStatus = "passed" | "needs_review" | "failed";

interface CLISegment {
  name: string;
  status: string;
}

interface CLIJsonOutput {
  status: CLIStatus;
  exit_code: number;
  merged_markdown: string | null;
  review_markdown: string | null;
  rerun_segments: CLISegment[];
}

interface MCPToolOutput {
  status: MCPStatus;
  exit_code: number;
  merged_markdown: string | null;
  review_markdown: string | null;
  rerun_segments: CLISegment[];
  stdout: string;
  stderr: string;
}

// ============================================================
// Project root detection
// ============================================================

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
// Source: mcp/server/src/index.ts → compiled: mcp/server/dist/index.js
// Project root is 3 levels up from the source directory
const PROJECT_ROOT = path.resolve(__dirname, "..", "..", "..");

// ============================================================
// Status mapping
// ============================================================

function mapStatus(cliStatus: CLIStatus): MCPStatus {
  switch (cliStatus) {
    case "all_passed":
      return "passed";
    case "needs_review":
      return "needs_review";
    case "error":
      return "failed";
    default: {
      const _exhaustive: never = cliStatus;
      return "failed";
    }
  }
}

// ============================================================
// Input validation
// ============================================================

async function validateInputs(
  pdfPath: string,
  segmentsDir: string,
): Promise<{ ok: true } | { ok: false; error: string }> {
  // Check PDF extension
  if (!pdfPath.toLowerCase().endsWith(".pdf")) {
    return { ok: false, error: `pdf_path must be a .pdf file: ${pdfPath}` };
  }

  // Check PDF exists and is a file
  let pdfStat;
  try {
    pdfStat = await fs.stat(pdfPath);
  } catch {
    return { ok: false, error: `pdf_path does not exist: ${pdfPath}` };
  }
  if (!pdfStat.isFile()) {
    return { ok: false, error: `pdf_path is not a file: ${pdfPath}` };
  }

  // Check segments dir exists and is a directory
  let segStat;
  try {
    segStat = await fs.stat(segmentsDir);
  } catch {
    return { ok: false, error: `segments_dir does not exist: ${segmentsDir}` };
  }
  if (!segStat.isDirectory()) {
    return { ok: false, error: `segments_dir is not a directory: ${segmentsDir}` };
  }

  return { ok: true };
}

// ============================================================
// Subprocess execution
// ============================================================

async function runPdfAuto(
  pdfPath: string,
  segmentsDir: string,
  threshold: number,
  rerunEffort: string,
  mergeOutput: string | undefined,
): Promise<{ stdout: string; stderr: string; exitCode: number }> {
  const scriptPath = path.join(PROJECT_ROOT, "scripts", "pdf-auto");

  const env: Record<string, string> = {
    ...process.env,
    PDF_AUTO_JSON: "1",
    PDF_VALIDATE_THRESHOLD: String(threshold),
    MINERU_RERUN_EFFORT: rerunEffort,
  };

  if (mergeOutput) {
    env.PDF_AUTO_MERGE_OUTPUT = mergeOutput;
  }

  const child = spawn("bash", [scriptPath, pdfPath, segmentsDir], {
    cwd: PROJECT_ROOT,
    env,
    timeout: 600_000,
    stdio: ["ignore", "pipe", "pipe"],
  });

  let stdout = "";
  let stderr = "";

  child.stdout.on("data", (chunk: Buffer) => { stdout += chunk.toString(); });
  child.stderr.on("data", (chunk: Buffer) => {
    const text = chunk.toString();
    stderr += text;
    process.stderr.write(text);  // 实时透传到 Claude Code
  });

  const exitCode: number = await new Promise((resolve, reject) => {
    child.on("close", resolve);
    child.on("error", reject);
  });

  return { stdout, stderr, exitCode };
}

// ============================================================
// JSON parsing
// ============================================================

function parseCliOutput(
  stdout: string,
): { ok: true; data: CLIJsonOutput } | { ok: false; error: string } {
  const trimmed = stdout.trim();
  if (!trimmed) {
    return { ok: false, error: "pdf-auto produced empty stdout" };
  }

  // Defensive: extract JSON object boundaries in case stdout has extra content
  const firstBrace = trimmed.indexOf("{");
  const lastBrace = trimmed.lastIndexOf("}");
  const jsonStr =
    firstBrace >= 0 && lastBrace > firstBrace
      ? trimmed.slice(firstBrace, lastBrace + 1)
      : trimmed;

  let parsed: unknown;
  try {
    parsed = JSON.parse(jsonStr);
  } catch (err) {
    return {
      ok: false,
      error: `Failed to parse CLI JSON: ${err instanceof Error ? err.message : String(err)}`,
    };
  }

  // Runtime structural validation
  if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
    return { ok: false, error: "CLI output is not a JSON object" };
  }

  const obj = parsed as Record<string, unknown>;

  if (
    typeof obj.status !== "string" ||
    !["all_passed", "needs_review", "error"].includes(obj.status)
  ) {
    return { ok: false, error: `Unknown or missing CLI status: ${obj.status}` };
  }

  if (typeof obj.exit_code !== "number") {
    return { ok: false, error: `Missing or invalid exit_code in CLI output` };
  }

  return { ok: true, data: parsed as CLIJsonOutput };
}

// ============================================================
// Serialize output
// ============================================================

function formatOutput(output: MCPToolOutput): string {
  return JSON.stringify(output, null, 2);
}

function buildFailedOutput(
  exitCode: number,
  stdout: string,
  stderr: string,
  extraError?: string,
): MCPToolOutput {
  return {
    status: "failed",
    exit_code: exitCode,
    merged_markdown: null,
    review_markdown: null,
    rerun_segments: [],
    stdout,
    stderr: extraError ? `${stderr}\n${extraError}` : stderr,
  };
}

// ============================================================
// Main — MCP Server
// ============================================================

async function main() {
  console.error("[mcp] Starting mineru-pdf-workflow MCP server...");

  const server = new McpServer({
    name: "mineru-pdf-workflow",
    version: "1.0.0",
  });

  server.tool(
    "run_pdf_auto",
    "运行自动化 PDF 解析流水线（分段解析→验证→可疑段重跑→再验证→合并→人工兜底清单）。\n" +
      "封装 scripts/pdf-auto，内部调用 PDF_AUTO_JSON=1 scripts/pdf-auto <pdf> <segments_dir>，\n" +
      "将 CLI JSON 输出映射为结构化工具返回值。\n\n" +
      "状态说明：\n" +
      "- passed：全部段通过验证，合并完成\n" +
      "- needs_review：存在需人工复核的段，未合并。确认后运行 pdf-merge 手动合并。\n" +
      "- failed：脚本错误或调用失败",
    {
      pdf_path: z
        .string()
        .describe("绝对路径，指向需要解析的 .pdf 文件"),
      segments_dir: z
        .string()
        .describe("绝对路径，指向已存在的分段目录（如 xxx-mineru-segments/）"),
      threshold: z
        .number()
        .min(0)
        .max(1)
        .default(0.82)
        .describe("覆盖率验证阈值（0-1），默认 0.82"),
      rerun_effort: z
        .enum(["high", "medium", "low"])
        .default("high")
        .describe("可疑段重跑精度，默认 high"),
      merge_output: z
        .string()
        .optional()
        .describe("自定义合并 Markdown 输出路径（可选，默认自动推导）"),
    },
    async ({ pdf_path, segments_dir, threshold, rerun_effort, merge_output }) => {
      console.error(
        `[mcp] run_pdf_auto called: pdf=${pdf_path}, seg=${segments_dir}, ` +
          `threshold=${threshold}, effort=${rerun_effort}, merge=${merge_output ?? "auto"}`,
      );

      // Step 1: Validate inputs
      const valid = await validateInputs(pdf_path, segments_dir);
      if (!valid.ok) {
        console.error(`[mcp] Validation failed: ${valid.error}`);
        const output = buildFailedOutput(1, "", valid.error);
        return { content: [{ type: "text" as const, text: formatOutput(output) }] };
      }

      // Step 2: Run pdf-auto (stderr streams in real-time)
      const result = await runPdfAuto(
        pdf_path,
        segments_dir,
        threshold,
        rerun_effort,
        merge_output,
      );
      const { stdout, stderr, exitCode } = result;

      // exit code 0 = all_passed, 2 = needs_review — both valid
      if (exitCode !== 0 && exitCode !== 2) {
        console.error(`[mcp] pdf-auto exited with code ${exitCode}`);
        const output = buildFailedOutput(
          exitCode,
          stdout,
          stderr,
          `pdf-auto exited with code ${exitCode}`,
        );
        return { content: [{ type: "text" as const, text: formatOutput(output) }] };
      }

      // Step 3: Parse CLI JSON output
      const parsed = parseCliOutput(stdout);
      if (!parsed.ok) {
        console.error(`[mcp] Parse error: ${parsed.error}`);
        const output = buildFailedOutput(
          1,
          stdout,
          stderr,
          parsed.error,
        );
        return { content: [{ type: "text" as const, text: formatOutput(output) }] };
      }

      // Step 4: Map and return
      const mcpStatus = mapStatus(parsed.data.status);
      console.error(
        `[mcp] CLI status=${parsed.data.status} → MCP status=${mcpStatus}, exit=${parsed.data.exit_code}`,
      );

      const output: MCPToolOutput = {
        status: mcpStatus,
        exit_code: parsed.data.exit_code,
        merged_markdown: parsed.data.merged_markdown,
        review_markdown: parsed.data.review_markdown,
        rerun_segments: parsed.data.rerun_segments ?? [],
        stdout,
        stderr,
      };

      return { content: [{ type: "text" as const, text: formatOutput(output) }] };
    },
  );

  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("[mcp] mineru-pdf-workflow MCP server ready (stdio)");
}

main().catch((err) => {
  console.error("[mcp] Fatal:", err);
  process.exit(1);
});
