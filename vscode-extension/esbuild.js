const esbuild = require("esbuild");

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

  // re-enabled in Task 4 once src/webview/main.ts exists
  // await esbuild.build({
  //   ...shared,
  //   entryPoints: ["src/webview/main.ts"],
  //   outfile: "dist/webview/main.js",
  //   platform: "browser",
  //   format: "iife",
  // });
}

build().catch((err) => {
  console.error(err);
  process.exit(1);
});
