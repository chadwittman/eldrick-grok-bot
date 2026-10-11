/**
 * ELDRICK Club Fitter on Grok (TypeScript). The same chat as
 * ../python/grok_fitter.py, through xAI's OpenAI-compatible Responses API
 * with plain fetch, so it needs no packages beyond Node 20 and tsx.
 *
 *   export XAI_API_KEY=... ELDRICK_API_KEY=eld_...
 *   npx tsx typescript/grok-fitter.ts
 *   npx tsx typescript/grok-fitter.ts --print-config
 *
 * xAI runs the MCP connection server-side: every turn sends ELDRICK as a
 * `{ type: "mcp" }` tool and xAI calls https://api.eldrick.com/mcp itself.
 * Docs: https://docs.x.ai/developers/tools/remote-mcp
 */
import { readFileSync } from "node:fs";
import { createInterface } from "node:readline/promises";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const TEMPLATE_DIR = join(dirname(fileURLToPath(import.meta.url)), "..");
export const XAI_RESPONSES_URL = "https://api.x.ai/v1/responses";

export interface EldrickMcpTool {
  type: "mcp";
  server_url: string;
  server_label: string;
  server_description?: string;
  allowed_tools?: string[];
  authorization?: string;
  headers?: Record<string, string>;
}

interface TemplateConfig { tool: EldrickMcpTool; freeTools: string[]; model: string }

export function loadConfig(): TemplateConfig {
  return JSON.parse(readFileSync(join(TEMPLATE_DIR, "eldrick-mcp.json"), "utf8"));
}

export const systemPrompt = () => readFileSync(join(TEMPLATE_DIR, "system-prompt.md"), "utf8");

/** ELDRICK as a Responses API `mcp` tool. The key comes from the caller (the environment), never from source. */
export function eldrickTool(config: TemplateConfig, eldrickApiKey?: string, env: NodeJS.ProcessEnv = process.env): EldrickMcpTool {
  const tool: EldrickMcpTool = { ...config.tool, server_url: env.ELDRICK_MCP_URL || config.tool.server_url, headers: { ...config.tool.headers } };
  if (eldrickApiKey) tool.authorization = eldrickApiKey;
  return tool;
}

/** The text of a Responses API result, and the MCP tools it called. */
export function readOutput(body: any): { text: string; toolCalls: string[] } {
  const text: string[] = [];
  const toolCalls: string[] = [];
  for (const item of body?.output ?? []) {
    if (item?.type === "message") for (const part of item.content ?? []) if (part?.type === "output_text") text.push(part.text);
    if (item?.type === "mcp_call" && item.name) toolCalls.push(String(item.name));
  }
  return { text: text.join("\n").trim(), toolCalls };
}

async function chatLoop(): Promise<void> {
  const xaiKey = process.env.XAI_API_KEY?.trim();
  const eldrickKey = process.env.ELDRICK_API_KEY?.trim();
  if (!xaiKey || !eldrickKey) throw new Error("Set XAI_API_KEY (console.x.ai) and ELDRICK_API_KEY (api.eldrick.com). See ../.env.example.");
  const config = loadConfig();
  const model = process.env.GROK_MODEL || config.model;
  const tools = [eldrickTool(config, eldrickKey)];
  let previousResponseId: string | null = null;

  const rl = createInterface({ input: process.stdin, output: process.stdout });
  console.log("ELDRICK Club Fitter on Grok");
  console.log("Which club do you want fitted: driver, fairway wood, hybrid, irons or wedges? (exit to quit)\n");
  try {
    for (;;) {
      const text = (await rl.question("You: ")).trim();
      if (!text) continue;
      if (/^(exit|quit)$/i.test(text)) return;
      // The system prompt goes in the first turn; later turns chain on previous_response_id
      // (xAI does not allow `instructions` together with previous_response_id).
      const input = previousResponseId ? [{ role: "user", content: text }] : [{ role: "system", content: systemPrompt() }, { role: "user", content: text }];
      const res = await fetch(XAI_RESPONSES_URL, {
        method: "POST",
        headers: { Authorization: `Bearer ${xaiKey}`, "Content-Type": "application/json" },
        body: JSON.stringify({ model, input, tools, previous_response_id: previousResponseId ?? undefined }),
      });
      const body: any = await res.json().catch(() => ({}));
      if (!res.ok) { console.error(`\nxAI error ${res.status}: ${body?.error?.message ?? body?.error ?? "unknown"}\n`); continue; }
      previousResponseId = body.id ?? previousResponseId;
      const { text: reply, toolCalls } = readOutput(body);
      for (const name of toolCalls) console.log(`  [called ${name}]`);
      console.log(`\nELDRICK: ${reply}\n`);
    }
  } finally {
    rl.close();
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  if (process.argv.includes("--print-config")) {
    const config = loadConfig();
    const tool = eldrickTool(config, process.env.ELDRICK_API_KEY);
    console.log(JSON.stringify({ model: process.env.GROK_MODEL || config.model, responses_api_tool: { ...tool, ...(tool.authorization ? { authorization: "<ELDRICK_API_KEY from env>" } : {}) } }, null, 2));
  } else {
    chatLoop().catch((error) => { console.error(error instanceof Error ? error.message : error); process.exit(1); });
  }
}
