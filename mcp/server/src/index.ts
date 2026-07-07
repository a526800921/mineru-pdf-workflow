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
  status: string;
  exit_code: number;
  merged_markdown?: string | null;
  review_markdown?: string | null;
  rerun_segments?: CLISegment[];
  stdout: string;
  stderr: string;
  [key: string]: unknown;
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
// Status mapping (for run_pdf_auto)
// ============================================================

function mapStatus(cliStatus: CLIStatus): string {
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
  if (!pdfPath.toLowerCase().endsWith(".pdf")) {
    return { ok: false, error: `pdf_path must be a .pdf file: ${pdfPath}` };
  }

  let pdfStat;
  try {
    pdfStat = await fs.stat(pdfPath);
  } catch {
    return { ok: false, error: `pdf_path does not exist: ${pdfPath}` };
  }
  if (!pdfStat.isFile()) {
    return { ok: false, error: `pdf_path is not a file: ${pdfPath}` };
  }

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

async function validatePdfPath(
  pdfPath: string,
): Promise<{ ok: true } | { ok: false; error: string }> {
  if (!pdfPath.toLowerCase().endsWith(".pdf")) {
    return { ok: false, error: `pdf_path must be a .pdf file: ${pdfPath}` };
  }
  try {
    const stat = await fs.stat(pdfPath);
    if (!stat.isFile()) {
      return { ok: false, error: `pdf_path is not a file: ${pdfPath}` };
    }
  } catch {
    return { ok: false, error: `pdf_path does not exist: ${pdfPath}` };
  }
  return { ok: true };
}

async function validateDir(
  dirPath: string,
  label: string,
): Promise<{ ok: true } | { ok: false; error: string }> {
  try {
    const stat = await fs.stat(dirPath);
    if (!stat.isDirectory()) {
      return { ok: false, error: `${label} is not a directory: ${dirPath}` };
    }
  } catch {
    return { ok: false, error: `${label} does not exist: ${dirPath}` };
  }
  return { ok: true };
}

// ============================================================
// Generic subprocess execution
// ============================================================

interface RunScriptOptions {
  scriptPath: string;
  args: string[];
  env?: Record<string, string>;
  timeout?: number;
  logLabel: string;
}

async function runScript(
  opts: RunScriptOptions,
): Promise<{ stdout: string; stderr: string; exitCode: number }> {
  const { scriptPath, args, env, timeout = 600_000, logLabel } = opts;

  const childEnv: Record<string, string> = {
    ...Object.fromEntries(
      Object.entries(process.env).filter(([, v]) => v !== undefined) as [string, string][]
    ),
    ...env,
  };

  const child = spawn("bash", [scriptPath, ...args], {
    cwd: PROJECT_ROOT,
    env: childEnv,
    timeout,
    stdio: ["ignore", "pipe", "pipe"],
  });

  let stdout = "";
  let stderr = "";

  child.stdout.on("data", (chunk: Buffer) => {
    stdout += chunk.toString();
  });
  child.stderr.on("data", (chunk: Buffer) => {
    const text = chunk.toString();
    stderr += text;
    process.stderr.write(text);
  });

  const exitCode: number = await new Promise((resolve, reject) => {
    child.on("close", resolve);
    child.on("error", reject);
  });

  return { stdout, stderr, exitCode };
}

// ============================================================
// run_pdf_auto — kept for backward compatibility
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
    PDF_AUTO_JSON: "1",
    PDF_VALIDATE_THRESHOLD: String(threshold),
    MINERU_RERUN_EFFORT: rerunEffort,
  };

  if (mergeOutput) {
    env.PDF_AUTO_MERGE_OUTPUT = mergeOutput;
  }

  return runScript({
    scriptPath,
    args: [pdfPath, segmentsDir],
    env,
    logLabel: "run_pdf_auto",
  });
}

// ============================================================
// JSON parsing
// ============================================================

function parseCliOutput(
  stdout: string,
): { ok: true; data: CLIJsonOutput } | { ok: false; error: string } {
  const trimmed = stdout.trim();
  if (!trimmed) {
    return { ok: false, error: "CLI produced empty stdout" };
  }

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

/** Parse generic CLI JSON output (any status string). */
function parseCliJson(
  stdout: string,
): { ok: true; data: Record<string, unknown> } | { ok: false; error: string } {
  const trimmed = stdout.trim();
  if (!trimmed) {
    return { ok: false, error: "CLI produced empty stdout" };
  }

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

  if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
    return { ok: false, error: "CLI output is not a JSON object" };
  }

  return { ok: true, data: parsed as Record<string, unknown> };
}

// ============================================================
// Serialize output
// ============================================================

function formatOutput(output: Record<string, unknown>): string {
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

  // ==========================================================
  // Tool 1: run_pdf_auto (existing, kept for backward compatibility)
  // ==========================================================

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

      const valid = await validateInputs(pdf_path, segments_dir);
      if (!valid.ok) {
        console.error(`[mcp] Validation failed: ${valid.error}`);
        const output = buildFailedOutput(1, "", valid.error);
        return { content: [{ type: "text" as const, text: formatOutput(output) }] };
      }

      const result = await runPdfAuto(
        pdf_path,
        segments_dir,
        threshold,
        rerun_effort,
        merge_output,
      );
      const { stdout, stderr, exitCode } = result;

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

      const parsed = parseCliOutput(stdout);
      if (!parsed.ok) {
        console.error(`[mcp] Parse error: ${parsed.error}`);
        const output = buildFailedOutput(1, stdout, stderr, parsed.error);
        return { content: [{ type: "text" as const, text: formatOutput(output) }] };
      }

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

  // ==========================================================
  // Tool 2: parse_pdf_segmented
  // ==========================================================

  server.tool(
    "parse_pdf_segmented",
    "分段解析 PDF 文件。\n" +
      "封装 scripts/pdf-seg，内部调用 PDF_SEG_JSON=1 scripts/pdf-seg <pdf>，\n" +
      "将 CLI JSON 输出映射为结构化工具返回值。\n\n" +
      "状态说明：\n" +
      "- completed：全部分段解析完成\n" +
      "- error：脚本错误或调用失败",
    {
      pdf_path: z
        .string()
        .describe("绝对路径，指向需要解析的 .pdf 文件"),
      segment_size: z
        .number()
        .int()
        .min(1)
        .default(8)
        .describe("每段页数，默认 8"),
      backend: z
        .enum(["hybrid-engine", "vlm-engine", "pipeline"])
        .default("hybrid-engine")
        .describe("MinerU 后端引擎，默认 hybrid-engine"),
      effort: z
        .enum(["medium", "high"])
        .default("medium")
        .describe("解析精度，默认 medium"),
      method: z
        .enum(["auto", "txt", "ocr"])
        .default("auto")
        .describe("文本提取方法，默认 auto"),
      lang: z
        .string()
        .default("ch")
        .describe("文档语言，默认 ch"),
    },
    async ({ pdf_path, segment_size, backend, effort, method, lang }) => {
      console.error(
        `[mcp] parse_pdf_segmented: pdf=${pdf_path}, size=${segment_size}, backend=${backend}`,
      );

      const valid = await validatePdfPath(pdf_path);
      if (!valid.ok) {
        console.error(`[mcp] Validation failed: ${valid.error}`);
        return {
          content: [
            {
              type: "text" as const,
              text: formatOutput(buildFailedOutput(1, "", valid.error)),
            },
          ],
        };
      }

      const scriptPath = path.join(PROJECT_ROOT, "scripts", "pdf-seg");
      const result = await runScript({
        scriptPath,
        args: [pdf_path],
        env: {
          PDF_SEG_JSON: "1",
          MINERU_SEGMENT_SIZE: String(segment_size),
          MINERU_BACKEND: backend,
          MINERU_EFFORT: effort,
          MINERU_METHOD: method,
          MINERU_LANG: lang,
        },
        logLabel: "parse_pdf_segmented",
      });

      const { stdout, stderr, exitCode } = result;

      if (exitCode !== 0) {
        console.error(`[mcp] pdf-seg exited with code ${exitCode}`);
        return {
          content: [
            {
              type: "text" as const,
              text: formatOutput(
                buildFailedOutput(
                  exitCode,
                  stdout,
                  stderr,
                  `pdf-seg exited with code ${exitCode}`,
                ),
              ),
            },
          ],
        };
      }

      const parsed = parseCliJson(stdout);
      if (!parsed.ok) {
        console.error(`[mcp] Parse error: ${parsed.error}`);
        return {
          content: [
            {
              type: "text" as const,
              text: formatOutput(buildFailedOutput(1, stdout, stderr, parsed.error)),
            },
          ],
        };
      }

      const output: MCPToolOutput = {
        status: String(parsed.data.status ?? "completed"),
        exit_code: exitCode,
        stdout,
        stderr,
        segments_dir: parsed.data.segments_dir,
        manifest_path: parsed.data.manifest_path,
        total_pages: parsed.data.total_pages,
        segment_size: parsed.data.segment_size,
        segments: parsed.data.segments,
      };

      return { content: [{ type: "text" as const, text: formatOutput(output) }] };
    },
  );

  // ==========================================================
  // Tool 3: validate_segments
  // ==========================================================

  server.tool(
    "validate_segments",
    "验证 MinerU 分段输出的文本覆盖率。\n" +
      "封装 scripts/pdf-validate，内部调用 PDF_VALIDATE_JSON=1 scripts/pdf-validate <pdf> <segments_dir>，\n" +
      "将 CLI JSON 输出映射为结构化工具返回值。\n\n" +
      "返回每个分段的覆盖率、状态（passed/suspicious/skipped/failed）、缺失 token 等。",
    {
      pdf_path: z
        .string()
        .describe("绝对路径，指向原始 .pdf 文件"),
      segments_dir: z
        .string()
        .describe("绝对路径，指向分段目录（如 xxx-mineru-segments/）"),
      threshold: z
        .number()
        .min(0)
        .max(1)
        .default(0.82)
        .describe("覆盖率阈值（0-1），默认 0.82"),
    },
    async ({ pdf_path, segments_dir, threshold }) => {
      console.error(
        `[mcp] validate_segments: pdf=${pdf_path}, seg=${segments_dir}, threshold=${threshold}`,
      );

      const validPdf = await validatePdfPath(pdf_path);
      if (!validPdf.ok) {
        return {
          content: [
            {
              type: "text" as const,
              text: formatOutput(buildFailedOutput(1, "", validPdf.error)),
            },
          ],
        };
      }

      const validDir = await validateDir(segments_dir, "segments_dir");
      if (!validDir.ok) {
        return {
          content: [
            {
              type: "text" as const,
              text: formatOutput(buildFailedOutput(1, "", validDir.error)),
            },
          ],
        };
      }

      const scriptPath = path.join(PROJECT_ROOT, "scripts", "pdf-validate");
      const result = await runScript({
        scriptPath,
        args: [pdf_path, segments_dir],
        env: {
          PDF_VALIDATE_JSON: "1",
          PDF_VALIDATE_THRESHOLD: String(threshold),
        },
        logLabel: "validate_segments",
      });

      const { stdout, stderr, exitCode } = result;

      // pdf-validate exits 1 when there are failed segments — that's valid output
      if (exitCode !== 0 && exitCode !== 1) {
        console.error(`[mcp] pdf-validate exited with code ${exitCode}`);
        return {
          content: [
            {
              type: "text" as const,
              text: formatOutput(
                buildFailedOutput(
                  exitCode,
                  stdout,
                  stderr,
                  `pdf-validate exited with code ${exitCode}`,
                ),
              ),
            },
          ],
        };
      }

      const parsed = parseCliJson(stdout);
      if (!parsed.ok) {
        console.error(`[mcp] Parse error: ${parsed.error}`);
        return {
          content: [
            {
              type: "text" as const,
              text: formatOutput(buildFailedOutput(1, stdout, stderr, parsed.error)),
            },
          ],
        };
      }

      const output: MCPToolOutput = {
        status: parsed.data.passed ? "all_passed" : "has_issues",
        exit_code: exitCode,
        stdout,
        stderr,
        passed: parsed.data.passed,
        threshold: parsed.data.threshold,
        segments: parsed.data.segments,
      };

      return { content: [{ type: "text" as const, text: formatOutput(output) }] };
    },
  );

  // ==========================================================
  // Tool 4: rerun_segments
  // ==========================================================

  server.tool(
    "rerun_segments",
    "对指定页高精度重跑 MinerU 解析，替换原分段结果，完成后自动合并。\n" +
      "封装 scripts/pdf-rerun，内部调用 PDF_RERUN_JSON=1 scripts/pdf-rerun <pdf> <segments_dir> <pages...>，\n" +
      "页码使用 1-based（与 PDF 页码一致）。\n\n" +
      "状态说明：\n" +
      "- completed：重跑完成并已合并\n" +
      "- error：脚本错误或调用失败",
    {
      pdf_path: z
        .string()
        .describe("绝对路径，指向原始 .pdf 文件"),
      segments_dir: z
        .string()
        .describe("绝对路径，指向分段目录（如 xxx-mineru-segments/）"),
      pages: z
        .array(z.number().int().min(1))
        .min(1)
        .describe("需要重跑的 PDF 页码列表（1-based，与 PDF 页码一致）"),
      effort: z
        .enum(["high", "medium", "low"])
        .default("high")
        .describe("重跑精度，默认 high"),
    },
    async ({ pdf_path, segments_dir, pages, effort }) => {
      console.error(
        `[mcp] rerun_segments: pdf=${pdf_path}, seg=${segments_dir}, pages=${pages.join(",")}, effort=${effort}`,
      );

      const validPdf = await validatePdfPath(pdf_path);
      if (!validPdf.ok) {
        return {
          content: [
            {
              type: "text" as const,
              text: formatOutput(buildFailedOutput(1, "", validPdf.error)),
            },
          ],
        };
      }

      const validDir = await validateDir(segments_dir, "segments_dir");
      if (!validDir.ok) {
        return {
          content: [
            {
              type: "text" as const,
              text: formatOutput(buildFailedOutput(1, "", validDir.error)),
            },
          ],
        };
      }

      const scriptPath = path.join(PROJECT_ROOT, "scripts", "pdf-rerun");
      const result = await runScript({
        scriptPath,
        args: [pdf_path, segments_dir, ...pages.map(String)],
        env: {
          PDF_RERUN_JSON: "1",
          MINERU_EFFORT: effort,
        },
        logLabel: "rerun_segments",
      });

      const { stdout, stderr, exitCode } = result;

      if (exitCode !== 0) {
        console.error(`[mcp] pdf-rerun exited with code ${exitCode}`);
        return {
          content: [
            {
              type: "text" as const,
              text: formatOutput(
                buildFailedOutput(
                  exitCode,
                  stdout,
                  stderr,
                  `pdf-rerun exited with code ${exitCode}`,
                ),
              ),
            },
          ],
        };
      }

      const parsed = parseCliJson(stdout);
      if (!parsed.ok) {
        console.error(`[mcp] Parse error: ${parsed.error}`);
        return {
          content: [
            {
              type: "text" as const,
              text: formatOutput(buildFailedOutput(1, stdout, stderr, parsed.error)),
            },
          ],
        };
      }

      const output: MCPToolOutput = {
        status: String(parsed.data.status ?? "completed"),
        exit_code: exitCode,
        stdout,
        stderr,
        rerun_count: parsed.data.rerun_count as number,
        merged_markdown: parsed.data.merged_markdown as string | null,
        segments: parsed.data.segments,
      };

      return { content: [{ type: "text" as const, text: formatOutput(output) }] };
    },
  );

  // ==========================================================
  // Tool 5: merge_segments
  // ==========================================================

  server.tool(
    "merge_segments",
    "合并分段 Markdown 为单一输出文件。\n" +
      "封装 scripts/pdf-merge，输出合并后的 Markdown 文件路径。\n\n" +
      "状态说明：\n" +
      "- completed：合并完成\n" +
      "- failed：脚本错误或调用失败",
    {
      segments_dir: z
        .string()
        .describe("绝对路径，指向分段目录（如 xxx-mineru-segments/）"),
      merge_output: z
        .string()
        .optional()
        .describe("自定义合并 Markdown 输出路径（可选，默认自动推导）"),
    },
    async ({ segments_dir, merge_output }) => {
      console.error(
        `[mcp] merge_segments: seg=${segments_dir}, merge=${merge_output ?? "auto"}`,
      );

      const validDir = await validateDir(segments_dir, "segments_dir");
      if (!validDir.ok) {
        return {
          content: [
            {
              type: "text" as const,
              text: formatOutput(buildFailedOutput(1, "", validDir.error)),
            },
          ],
        };
      }

      const scriptPath = path.join(PROJECT_ROOT, "scripts", "pdf-merge");
      const env: Record<string, string> = {};
      if (merge_output) {
        env.PDF_MERGE_OUTPUT = merge_output;
      }

      const result = await runScript({
        scriptPath,
        args: [segments_dir],
        env,
        logLabel: "merge_segments",
      });

      const { stdout, stderr, exitCode } = result;

      if (exitCode !== 0) {
        console.error(`[mcp] pdf-merge exited with code ${exitCode}`);
        return {
          content: [
            {
              type: "text" as const,
              text: formatOutput(
                buildFailedOutput(
                  exitCode,
                  stdout,
                  stderr,
                  `pdf-merge exited with code ${exitCode}`,
                ),
              ),
            },
          ],
        };
      }

      // pdf-merge doesn't have JSON mode; extract the output path from stdout
      const outMatch = stdout.match(/输出文件:\s*(.+)/);
      const mergedPath = outMatch ? outMatch[1].trim() : null;

      const output: MCPToolOutput = {
        status: "completed",
        exit_code: exitCode,
        stdout,
        stderr,
        merged_markdown: mergedPath,
      };

      return { content: [{ type: "text" as const, text: formatOutput(output) }] };
    },
  );

  // ==========================================================
  // Tool 6: create_review_report
  // ==========================================================

  server.tool(
    "create_review_report",
    "从 pdf-validate 的 JSON 报告生成人工兜底清单 Markdown（review.md）。\n" +
      "封装 scripts/pdf-review，提取需人工复核的分段和页面，生成结构化 review 文档。\n\n" +
      "状态说明：\n" +
      "- completed：review 报告生成完成\n" +
      "- failed：脚本错误或调用失败",
    {
      validate_json: z
        .string()
        .describe("pdf-validate JSON 报告文件路径（PDF_VALIDATE_JSON=1 输出）"),
      review_output: z
        .string()
        .describe("输出 review.md 的路径"),
      threshold: z
        .number()
        .min(0)
        .max(1)
        .describe("覆盖率阈值（与验证时一致）"),
      pdf_path: z
        .string()
        .describe("原始 PDF 文件路径"),
      segments_dir: z
        .string()
        .describe("分段目录路径"),
      rerun_failures: z
        .string()
        .optional()
        .describe("空格分隔的重跑失败分段名（可选）"),
    },
    async ({ validate_json, review_output, threshold, pdf_path, segments_dir, rerun_failures }) => {
      console.error(
        `[mcp] create_review_report: validate=${validate_json}, review=${review_output}`,
      );

      // Validate inputs
      try {
        await fs.stat(validate_json);
      } catch {
        return {
          content: [
            {
              type: "text" as const,
              text: formatOutput(
                buildFailedOutput(1, "", `validate_json does not exist: ${validate_json}`),
              ),
            },
          ],
        };
      }

      const scriptPath = path.join(PROJECT_ROOT, "scripts", "pdf-review");
      const args = [
        validate_json,
        review_output,
        String(threshold),
        pdf_path,
        segments_dir,
      ];
      if (rerun_failures) {
        args.push(rerun_failures);
      }

      const result = await runScript({
        scriptPath,
        args,
        logLabel: "create_review_report",
      });

      const { stdout, stderr, exitCode } = result;

      if (exitCode !== 0) {
        console.error(`[mcp] pdf-review exited with code ${exitCode}`);
        return {
          content: [
            {
              type: "text" as const,
              text: formatOutput(
                buildFailedOutput(
                  exitCode,
                  stdout,
                  stderr,
                  `pdf-review exited with code ${exitCode}`,
                ),
              ),
            },
          ],
        };
      }

      const output: MCPToolOutput = {
        status: "completed",
        exit_code: exitCode,
        stdout,
        stderr,
        review_markdown: review_output,
      };

      return { content: [{ type: "text" as const, text: formatOutput(output) }] };
    },
  );

  // ==========================================================
  // Tool 7: read_page
  // ==========================================================

  server.tool(
    "read_page",
    "按 PDF 页码读取合并 Markdown 中对应片段。\n" +
      "封装 scripts/pdf-read-page，内部调用 PDF_READ_PAGE_JSON=1 scripts/pdf-read-page <package_dir> <page> [page_end]，\n" +
      "将 CLI JSON 输出映射为结构化工具返回值。\n\n" +
      "合并 Markdown 由 <!-- pages N-M --> 锚点分节，该工具按页码定位对应段并返回 Markdown 文本。\n" +
      "若合并 Markdown 不存在，回退到 segments/ 目录查找。",
    {
      package_dir: z
        .string()
        .describe("输出包根目录（含 <stem>.md 和 segments/）的绝对路径"),
      page: z
        .number()
        .int()
        .min(1)
        .describe("PDF 页码（1-based），会定位到包含该页的 <!-- pages N-M --> 段"),
      page_end: z
        .number()
        .int()
        .min(1)
        .optional()
        .describe("结束页码，指定后返回连续多段的 Markdown"),
    },
    async ({ package_dir, page, page_end }) => {
      console.error(
        `[mcp] read_page: pkg=${package_dir}, page=${page}, page_end=${page_end ?? "auto"}`,
      );

      const validDir = await validateDir(package_dir, "package_dir");
      if (!validDir.ok) {
        return {
          content: [
            {
              type: "text" as const,
              text: formatOutput(buildFailedOutput(1, "", validDir.error)),
            },
          ],
        };
      }

      const scriptPath = path.join(PROJECT_ROOT, "scripts", "pdf-read-page");
      const args = [package_dir, String(page)];
      if (page_end !== undefined) {
        args.push(String(page_end));
      }

      const result = await runScript({
        scriptPath,
        args,
        env: { PDF_READ_PAGE_JSON: "1" },
        logLabel: "read_page",
      });

      const { stdout, stderr, exitCode } = result;

      if (exitCode !== 0) {
        console.error(`[mcp] pdf-read-page exited with code ${exitCode}`);
        return {
          content: [
            {
              type: "text" as const,
              text: formatOutput(
                buildFailedOutput(
                  exitCode,
                  stdout,
                  stderr,
                  `pdf-read-page exited with code ${exitCode}`,
                ),
              ),
            },
          ],
        };
      }

      const parsed = parseCliJson(stdout);
      if (!parsed.ok) {
        console.error(`[mcp] Parse error: ${parsed.error}`);
        return {
          content: [
            {
              type: "text" as const,
              text: formatOutput(buildFailedOutput(1, stdout, stderr, parsed.error)),
            },
          ],
        };
      }

      const output: MCPToolOutput = {
        status: String(parsed.data.status ?? "completed"),
        exit_code: exitCode,
        stdout,
        stderr,
        page: parsed.data.page,
        page_start: parsed.data.page_start,
        page_end: parsed.data.page_end,
        section_path: parsed.data.section_path,
        segment_count: parsed.data.segment_count,
        markdown: parsed.data.markdown,
      };

      return { content: [{ type: "text" as const, text: formatOutput(output) }] };
    },
  );

  // ==========================================================
  // Tool 8: search_pdf_content
  // ==========================================================

  server.tool(
    "search_pdf_content",
    "在输出包中搜索关键词，检索合并 Markdown 和 quick_lookup_draft.csv。\n" +
      "封装 scripts/pdf-search-content，内部调用 PDF_SEARCH_CONTENT_JSON=1 scripts/pdf-search-content <package_dir> <query>，\n" +
      "将 CLI JSON 输出映射为结构化工具返回值。\n\n" +
      "多个词用空格分隔，全部匹配（AND 逻辑）。返回统一结果列表（含来源、页码、章节、原文片段）。",
    {
      package_dir: z
        .string()
        .describe("输出包根目录（含 <stem>.md 和 data/quick_lookup_draft.csv）的绝对路径"),
      query: z
        .string()
        .describe("搜索关键词（支持空格分隔的多个词，AND 匹配）"),
      max_results: z
        .number()
        .int()
        .min(1)
        .max(50)
        .default(10)
        .describe("最大返回数，默认 10"),
      source: z
        .enum(["all", "markdown", "csv"])
        .default("all")
        .describe("搜索数据源：all（默认）/ markdown / csv"),
    },
    async ({ package_dir, query, max_results, source }) => {
      console.error(
        `[mcp] search_pdf_content: pkg=${package_dir}, query=${query}, max=${max_results}, src=${source}`,
      );

      const validDir = await validateDir(package_dir, "package_dir");
      if (!validDir.ok) {
        return {
          content: [
            {
              type: "text" as const,
              text: formatOutput(buildFailedOutput(1, "", validDir.error)),
            },
          ],
        };
      }

      if (!query.trim()) {
        const output = buildFailedOutput(1, "", "query must not be empty");
        return {
          content: [{ type: "text" as const, text: formatOutput(output) }],
        };
      }

      const scriptPath = path.join(PROJECT_ROOT, "scripts", "pdf-search-content");
      const args = [package_dir, query, "-s", source, "-m", String(max_results)];

      const result = await runScript({
        scriptPath,
        args,
        env: { PDF_SEARCH_CONTENT_JSON: "1" },
        logLabel: "search_pdf_content",
      });

      const { stdout, stderr, exitCode } = result;

      if (exitCode !== 0) {
        console.error(`[mcp] pdf-search-content exited with code ${exitCode}`);
        return {
          content: [
            {
              type: "text" as const,
              text: formatOutput(
                buildFailedOutput(
                  exitCode,
                  stdout,
                  stderr,
                  `pdf-search-content exited with code ${exitCode}`,
                ),
              ),
            },
          ],
        };
      }

      const parsed = parseCliJson(stdout);
      if (!parsed.ok) {
        console.error(`[mcp] Parse error: ${parsed.error}`);
        return {
          content: [
            {
              type: "text" as const,
              text: formatOutput(buildFailedOutput(1, stdout, stderr, parsed.error)),
            },
          ],
        };
      }

      const output: MCPToolOutput = {
        status: String(parsed.data.status ?? "completed"),
        exit_code: exitCode,
        stdout,
        stderr,
        query: parsed.data.query,
        total_matches: parsed.data.total_matches,
        results: parsed.data.results,
      };

      return { content: [{ type: "text" as const, text: formatOutput(output) }] };
    },
  );

  // ==========================================================
  // Tool 9: export_chunks
  // ==========================================================

  server.tool(
    "export_chunks",
    "将合并 Markdown 预处理为 chunks.jsonl，供下游向量化。\n" +
      "封装 scripts/pdf-export-chunks，内部按 ## 标题切分、HTML 表格展开、图片替换、Markdown 清洗、token 上限裁剪。\n" +
      "输出到 <package>/data/chunks.jsonl，每行一个 JSON 块（id/content/page/section/token_count）。",
    {
      package_dir: z
        .string()
        .describe("输出包根目录（含 <stem>.md 和 manifest.json）的绝对路径"),
      output_path: z
        .string()
        .optional()
        .describe("自定义 JSONL 输出路径（可选，默认 <package>/data/chunks.jsonl）"),
    },
    async ({ package_dir, output_path }) => {
      console.error(
        `[mcp] export_chunks: pkg=${package_dir}, out=${output_path ?? "auto"}`,
      );

      const validDir = await validateDir(package_dir, "package_dir");
      if (!validDir.ok) {
        return {
          content: [
            {
              type: "text" as const,
              text: formatOutput(buildFailedOutput(1, "", validDir.error)),
            },
          ],
        };
      }

      const scriptPath = path.join(PROJECT_ROOT, "scripts", "pdf-export-chunks");
      const args = [package_dir];
      if (output_path) {
        args.push(output_path);
      }

      const result = await runScript({
        scriptPath,
        args,
        env: { PDF_EXPORT_CHUNKS_JSON: "1" },
        logLabel: "export_chunks",
      });

      const { stdout, stderr, exitCode } = result;

      if (exitCode !== 0) {
        console.error(`[mcp] pdf-export-chunks exited with code ${exitCode}`);
        return {
          content: [
            {
              type: "text" as const,
              text: formatOutput(
                buildFailedOutput(
                  exitCode,
                  stdout,
                  stderr,
                  `pdf-export-chunks exited with code ${exitCode}`,
                ),
              ),
            },
          ],
        };
      }

      const parsed = parseCliJson(stdout);
      if (!parsed.ok) {
        console.error(`[mcp] Parse error: ${parsed.error}`);
        return {
          content: [
            {
              type: "text" as const,
              text: formatOutput(buildFailedOutput(1, stdout, stderr, parsed.error)),
            },
          ],
        };
      }

      const output: MCPToolOutput = {
        status: String(parsed.data.status ?? "completed"),
        exit_code: exitCode,
        stdout,
        stderr,
        chunk_count: parsed.data.chunk_count,
        output_path: parsed.data.output_path,
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
