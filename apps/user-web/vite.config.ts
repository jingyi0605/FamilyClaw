// @ts-nocheck
import { request as httpRequest } from "node:http";
import { URL } from "node:url";

import react from "@vitejs/plugin-react";
import type { IncomingMessage, ServerResponse } from "node:http";
import type { Plugin } from "vite";
import { defineConfig } from "vite";

const apiTarget = "http://127.0.0.1:8000";
const streamPathPattern = /^\/api\/v1\/ai-config\/[^/]+\/butler-bootstrap\/sessions\/[^/]+\/stream-messages(?:\?.*)?$/;

function sseProxyPlugin(): Plugin {
  return {
    name: "familyclaw-sse-proxy",
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        if (req.method !== "POST" || !req.url || !streamPathPattern.test(req.url)) {
          next();
          return;
        }

        void proxySseRequest(req, res).catch((error: unknown) => {
          server.config.logger.error(`[sse-proxy] ${error instanceof Error ? error.stack || error.message : String(error)}`);
          if (!res.headersSent) {
            res.writeHead(502, { "Content-Type": "application/json; charset=utf-8" });
          }
          res.end(JSON.stringify({ detail: "开发代理转发流式请求失败" }));
        });
      });
    },
  };
}

async function proxySseRequest(req: IncomingMessage, res: ServerResponse): Promise<void> {
  const body = await readRequestBody(req);
  const targetUrl = new URL(req.url || "/", apiTarget);
  res.shouldKeepAlive = false;

  await new Promise<void>((resolve, reject) => {
    const upstream = httpRequest(
      targetUrl,
      {
        method: req.method,
        headers: {
          ...filterHeaders(req.headers),
          host: targetUrl.host,
          accept: "text/event-stream",
          connection: "close",
          "cache-control": "no-cache",
          "content-length": Buffer.byteLength(body),
        },
      },
      (upstreamRes) => {
        res.writeHead(upstreamRes.statusCode || 200, {
          ...filterResponseHeaders(upstreamRes.headers),
          "content-type": "text/event-stream; charset=utf-8",
          "cache-control": "no-cache, no-transform",
          connection: "close",
          "x-accel-buffering": "no",
        });
        res.flushHeaders();

        upstreamRes.pipe(res, { end: true });
        upstreamRes.on("end", resolve);
        upstreamRes.on("error", reject);
      },
    );

    upstream.on("error", reject);
    req.on("aborted", () => upstream.destroy());
    res.on("close", () => upstream.destroy());
    upstream.write(body);
    upstream.end();
  });
}

function readRequestBody(req: IncomingMessage): Promise<Buffer> {
  return new Promise((resolve, reject) => {
    const chunks: Buffer[] = [];
    req.on("data", (chunk) => {
      chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
    });
    req.on("end", () => resolve(Buffer.concat(chunks)));
    req.on("error", reject);
  });
}

function filterHeaders(headers: IncomingMessage["headers"]): Record<string, string> {
  const result: Record<string, string> = {};
  for (const [key, value] of Object.entries(headers)) {
    if (!value) {
      continue;
    }
    if (["host", "connection", "content-length"].includes(key.toLowerCase())) {
      continue;
    }
    result[key] = Array.isArray(value) ? value.join(", ") : value;
  }
  return result;
}

function filterResponseHeaders(headers: IncomingMessage["headers"]): Record<string, string> {
  const result: Record<string, string> = {};
  for (const [key, value] of Object.entries(headers)) {
    if (!value) {
      continue;
    }
    if (["content-length", "content-encoding", "connection"].includes(key.toLowerCase())) {
      continue;
    }
    result[key] = Array.isArray(value) ? value.join(", ") : value;
  }
  return result;
}

export default defineConfig({
  plugins: [react(), sseProxyPlugin()],
  server: {
    proxy: {
      "/api": {
        target: apiTarget,
        changeOrigin: true,
      },
    },
  },
});
