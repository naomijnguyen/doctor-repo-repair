#!/usr/bin/env node

import { spawn } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import net from "node:net";
import os from "node:os";
import path from "node:path";
import process from "node:process";

const PROJECT_ROOT = path.resolve(import.meta.dirname, "..");
const temporaryRoot = mkdtempSync(path.join(os.tmpdir(), "field-notes-browser-"));
const chromeBinary = process.env.CHROME_BIN
  || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";

function reservePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const { port } = server.address();
      server.close(error => error ? reject(error) : resolve(port));
    });
  });
}

function delay(milliseconds) {
  return new Promise(resolve => setTimeout(resolve, milliseconds));
}

async function waitForHttp(url, processHandle, label) {
  const deadline = Date.now() + 8000;
  while (Date.now() < deadline) {
    if (processHandle.exitCode !== null) {
      throw new Error(`${label} exited before becoming ready`);
    }
    try {
      const response = await fetch(url);
      if (response.ok) return;
    } catch {
      // The process is still starting.
    }
    await delay(40);
  }
  throw new Error(`${label} did not become ready`);
}

class CdpSession {
  constructor(webSocketUrl) {
    this.nextId = 1;
    this.pending = new Map();
    this.listeners = new Map();
    this.socket = new WebSocket(webSocketUrl);
  }

  async open() {
    await new Promise((resolve, reject) => {
      this.socket.addEventListener("open", resolve, { once: true });
      this.socket.addEventListener("error", reject, { once: true });
    });
    this.socket.addEventListener("message", event => {
      const message = JSON.parse(event.data);
      if (message.id) {
        const pending = this.pending.get(message.id);
        if (!pending) return;
        this.pending.delete(message.id);
        if (message.error) pending.reject(new Error(message.error.message));
        else pending.resolve(message.result);
        return;
      }
      for (const listener of this.listeners.get(message.method) || []) {
        listener(message.params);
      }
    });
  }

  on(method, listener) {
    const listeners = this.listeners.get(method) || [];
    listeners.push(listener);
    this.listeners.set(method, listeners);
  }

  send(method, params = {}) {
    const id = this.nextId++;
    const promise = new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
    });
    this.socket.send(JSON.stringify({ id, method, params }));
    return promise;
  }

  async evaluate(expression) {
    const result = await this.send("Runtime.evaluate", {
      expression,
      awaitPromise: true,
      returnByValue: true,
    });
    if (result.exceptionDetails) {
      throw new Error(
        result.exceptionDetails.exception?.description
        || result.exceptionDetails.text
        || "browser evaluation failed",
      );
    }
    return result.result.value;
  }

  close() {
    this.socket.close();
  }
}

async function run() {
  const applicationPort = await reservePort();
  const debuggingPort = await reservePort();
  const applicationUrl = `http://127.0.0.1:${applicationPort}`;
  const server = spawn(process.env.PYTHON || "python3", ["-m", "fieldnotes.server"], {
    cwd: PROJECT_ROOT,
    env: {
      ...process.env,
      FIELDNOTES_PORT: String(applicationPort),
      FIELDNOTES_DATA: path.join(temporaryRoot, "browser.sqlite3"),
      PYTHONPYCACHEPREFIX: path.join(temporaryRoot, "python-cache"),
    },
    stdio: ["ignore", "pipe", "pipe"],
  });
  const chrome = spawn(chromeBinary, [
    "--headless=new",
    `--remote-debugging-port=${debuggingPort}`,
    `--user-data-dir=${path.join(temporaryRoot, "chrome-profile")}`,
    "--no-first-run",
    "--no-default-browser-check",
    "about:blank",
  ], { stdio: ["ignore", "ignore", "pipe"] });

  let session;
  try {
    await waitForHttp(`${applicationUrl}/api/notes`, server, "Field Notes server");
    await waitForHttp(`http://127.0.0.1:${debuggingPort}/json/version`, chrome, "Chrome");
    const target = await fetch(
      `http://127.0.0.1:${debuggingPort}/json/new?${encodeURIComponent(applicationUrl)}`,
      { method: "PUT" },
    ).then(response => response.json());
    session = new CdpSession(target.webSocketDebuggerUrl);
    await session.open();

    const browserErrors = [];
    session.on("Runtime.exceptionThrown", event => {
      browserErrors.push(event.exceptionDetails.text);
    });
    session.on("Log.entryAdded", event => {
      if (event.entry.level === "error") browserErrors.push(event.entry.text);
    });
    await session.send("Runtime.enable");
    await session.send("Log.enable");
    await session.send("Page.enable");
    await session.evaluate(`(async () => {
      const deadline = Date.now() + 5000;
      while (Date.now() < deadline) {
        if (document.readyState === "complete" && document.querySelector("#note-form")) return true;
        await new Promise(resolve => setTimeout(resolve, 20));
      }
      throw new Error("Field Notes page did not initialize");
    })()`);

    const initial = await session.evaluate(`({
      title: document.title,
      apiIsSameOrigin: !document.querySelector('script[src="app.js"]')?.src.includes('8000'),
      bodyWidth: document.documentElement.scrollWidth,
      viewportWidth: window.innerWidth,
    })`);
    if (initial.title !== "Field Notes" || initial.bodyWidth > initial.viewportWidth) {
      throw new Error(`desktop page failed layout check: ${JSON.stringify(initial)}`);
    }
    console.log("PASS desktop page loads from the application process");

    const delayedSave = await session.evaluate(`(async () => {
      const realFetch = window.fetch;
      let releaseSave;
      const saveGate = new Promise(resolve => { releaseSave = resolve; });
      window.fetch = async (url, options = {}) => {
        if (url === "/api/notes" && options.method === "POST") await saveGate;
        return realFetch(url, options);
      };
      const title = document.querySelector("#title");
      const body = document.querySelector("#body");
      const tags = document.querySelector("#tags");
      title.value = "Delayed observation";
      body.value = "Submitted body";
      tags.value = "Field Work";
      document.querySelector("#note-form").requestSubmit();
      body.value = "Newer draft typed while saving";
      releaseSave();
      const deadline = Date.now() + 5000;
      while (Date.now() < deadline) {
        if (document.querySelector("#status").textContent === "Note saved.") break;
        await new Promise(resolve => setTimeout(resolve, 20));
      }
      window.fetch = realFetch;
      return {
        title: title.value,
        body: body.value,
        tags: tags.value,
        heading: document.querySelector("article h2")?.textContent,
      };
    })()`);
    if (
      delayedSave.title !== ""
      || delayedSave.tags !== ""
      || delayedSave.body !== "Newer draft typed while saving"
      || delayedSave.heading !== "Delayed observation"
    ) {
      throw new Error(`slow save lost or misrendered draft state: ${JSON.stringify(delayedSave)}`);
    }
    console.log("PASS slow save preserves newer draft text");

    const orderedSearch = await session.evaluate(`(async () => {
      const realFetch = window.fetch;
      const response = note => new Response(JSON.stringify({ notes: [note] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
      window.fetch = (url, options) => {
        if (url === "/api/search?q=slow") {
          return new Promise(resolve => setTimeout(() => resolve(response({
            id: 90, title: "Slow result", body: "", tags: [],
            createdAt: "2026-09-18T00:00:00+00:00",
          })), 220));
        }
        if (url === "/api/search?q=fast") {
          return new Promise(resolve => setTimeout(() => resolve(response({
            id: 91, title: "Fast result", body: "", tags: [],
            createdAt: "2026-09-18T00:00:00+00:00",
          })), 10));
        }
        return realFetch(url, options);
      };
      const search = document.querySelector("#search");
      search.value = "slow";
      search.dispatchEvent(new Event("input", { bubbles: true }));
      await new Promise(resolve => setTimeout(resolve, 20));
      search.value = "fast";
      search.dispatchEvent(new Event("input", { bubbles: true }));
      await new Promise(resolve => setTimeout(resolve, 300));
      window.fetch = realFetch;
      return [...document.querySelectorAll("article h2")].map(node => node.textContent);
    })()`);
    if (JSON.stringify(orderedSearch) !== JSON.stringify(["Fast result"])) {
      throw new Error(`stale search overwrote the latest result: ${JSON.stringify(orderedSearch)}`);
    }
    console.log("PASS late search response cannot overwrite newer results");

    const refreshFailure = await session.evaluate(`(async () => {
      const realFetch = window.fetch;
      let failNextList = false;
      window.fetch = async (url, options = {}) => {
        if (url === "/api/notes" && options.method === "POST") {
          const result = await realFetch(url, options);
          failNextList = true;
          return result;
        }
        if (url === "/api/notes" && failNextList) {
          failNextList = false;
          throw new Error("controlled refresh failure");
        }
        return realFetch(url, options);
      };
      document.querySelector("#search").value = "";
      document.querySelector("#title").value = "Committed despite refresh";
      document.querySelector("#body").value = "";
      document.querySelector("#tags").value = "";
      document.querySelector("#note-form").requestSubmit();
      const deadline = Date.now() + 5000;
      while (Date.now() < deadline) {
        const status = document.querySelector("#status").textContent;
        if (status.includes("could not refresh")) break;
        await new Promise(resolve => setTimeout(resolve, 20));
      }
      const status = document.querySelector("#status").textContent;
      window.fetch = realFetch;
      return status;
    })()`);
    if (refreshFailure !== "Note saved, but the list could not refresh.") {
      throw new Error(`mutation success was mislabeled: ${refreshFailure}`);
    }
    console.log("PASS committed mutation remains success when refresh fails");

    const deleted = await session.evaluate(`(async () => {
      const search = document.querySelector("#search");
      search.value = "";
      search.dispatchEvent(new Event("input", { bubbles: true }));
      let deadline = Date.now() + 5000;
      while (Date.now() < deadline) {
        if (document.querySelector("#status").textContent === "Notes loaded.") break;
        await new Promise(resolve => setTimeout(resolve, 20));
      }
      const before = document.querySelectorAll("article").length;
      document.querySelector("article .delete").click();
      deadline = Date.now() + 5000;
      while (Date.now() < deadline) {
        if (document.querySelector("#status").textContent === "Note deleted.") break;
        await new Promise(resolve => setTimeout(resolve, 20));
      }
      return {
        before,
        after: document.querySelectorAll("article").length,
        status: document.querySelector("#status").textContent,
      };
    })()`);
    if (deleted.status !== "Note deleted." || deleted.after !== deleted.before - 1) {
      throw new Error(`delete workflow failed: ${JSON.stringify(deleted)}`);
    }
    console.log("PASS browser delete updates durable state and visible collection");

    await session.send("Emulation.setDeviceMetricsOverride", {
      width: 390,
      height: 844,
      deviceScaleFactor: 1,
      mobile: true,
    });
    const narrow = await session.evaluate(`({
      overflow: document.documentElement.scrollWidth > window.innerWidth,
      headingDirection: getComputedStyle(document.querySelector(".collection-heading")).flexDirection,
    })`);
    if (narrow.overflow || narrow.headingDirection !== "column") {
      throw new Error(`narrow layout failed: ${JSON.stringify(narrow)}`);
    }
    console.log("PASS narrow layout has no horizontal overflow");

    if (browserErrors.length) {
      throw new Error(`browser errors: ${browserErrors.join(" | ")}`);
    }
  } finally {
    session?.close();
    if (chrome.exitCode === null) chrome.kill("SIGTERM");
    if (server.exitCode === null) server.kill("SIGINT");
    await Promise.allSettled([
      chrome.exitCode === null
        ? new Promise(resolve => chrome.once("exit", resolve))
        : Promise.resolve(),
      server.exitCode === null
        ? new Promise(resolve => server.once("exit", resolve))
        : Promise.resolve(),
    ]);
    rmSync(temporaryRoot, { recursive: true, force: true });
  }
}

run().catch(error => {
  console.error(`FAIL ${error.stack || error}`);
  process.exitCode = 1;
});
