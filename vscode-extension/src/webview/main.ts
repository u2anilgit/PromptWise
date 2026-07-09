declare function acquireVsCodeApi(): { postMessage(message: unknown): void };

type Tab = "budget" | "security" | "governance";

const vscodeApi = acquireVsCodeApi();
let activeTab: Tab = "budget";

function render(): void {
  const app = document.getElementById("app");
  if (!app) return;
  app.innerHTML = `
    <div class="tabs">
      <div class="tab ${activeTab === "budget" ? "active" : ""}" data-tab="budget">Budget & Cost</div>
      <div class="tab ${activeTab === "security" ? "active" : ""}" data-tab="security">Security & Compliance</div>
      <div class="tab ${activeTab === "governance" ? "active" : ""}" data-tab="governance">Governance</div>
    </div>
    <div id="tile-content"></div>
    <button id="refresh-btn">Refresh</button>
    ${activeTab === "security" ? `
      <div>
        <textarea id="scan-input" placeholder="Paste text or code to scan"></textarea>
        <button id="scan-btn">Scan (security_check)</button>
      </div>
    ` : ""}
  `;

  document.querySelectorAll<HTMLElement>(".tab").forEach((el) => {
    el.addEventListener("click", () => {
      activeTab = el.dataset.tab as Tab;
      render();
      refresh();
    });
  });
  document.getElementById("refresh-btn")?.addEventListener("click", refresh);
  document.getElementById("scan-btn")?.addEventListener("click", () => {
    const input = document.getElementById("scan-input") as HTMLTextAreaElement | null;
    if (!input) return;
    vscodeApi.postMessage({ type: "scanText", kind: "security_check", text: input.value });
  });
}

function refresh(): void {
  vscodeApi.postMessage({ type: "refresh", tab: activeTab });
}

window.addEventListener("message", (event: MessageEvent) => {
  const message = event.data;
  const content = document.getElementById("tile-content");
  if (!content) return;
  if (message.type === "connectionError") {
    content.innerHTML = `<p class="error">Connection error: ${message.message}. Check the "promptwise.pythonPath" setting, and confirm pip install -e . has been run in this workspace.</p>`;
    return;
  }
  if (message.type === "tileError" && message.tab === activeTab) {
    content.innerHTML = `<p class="error">${message.message}</p>`;
    return;
  }
  if (message.type === "tileUpdate" && message.tab === activeTab) {
    content.innerHTML = `<pre>${JSON.stringify(message.data, null, 2)}</pre>`;
    return;
  }
  if (message.type === "scanResult") {
    content.innerHTML = `<pre>${message.text}</pre>`;
  }
});

render();
refresh();
