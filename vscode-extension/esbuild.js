const esbuild = require("esbuild");
const fs = require("fs");
const path = require("path");

const shared = {
  bundle: true,
  sourcemap: true,
  minify: false,
  logLevel: "info",
};

async function build() {
  await esbuild.build({
    ...shared,
    entryPoints: ["src/extension.ts"],
    outfile: "dist/extension.js",
    platform: "node",
    format: "cjs",
    external: ["vscode"],
  });

  await esbuild.build({
    ...shared,
    entryPoints: ["src/webview/main.ts"],
    outfile: "dist/webview/main.js",
    platform: "browser",
    format: "iife",
  });

  // esbuild only bundles JS entry points above; style.css is a static asset
  // the webview loads via a <link>, so it needs a plain copy into dist/.
  fs.mkdirSync(path.join(__dirname, "dist", "webview"), { recursive: true });
  fs.copyFileSync(
    path.join(__dirname, "src", "webview", "style.css"),
    path.join(__dirname, "dist", "webview", "style.css")
  );
}

build().catch((err) => {
  console.error(err);
  process.exit(1);
});
