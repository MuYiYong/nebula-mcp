import { fileURLToPath, URL } from "node:url";

import { defineConfig } from "vite";
import { viteSingleFile } from "vite-plugin-singlefile";

export default defineConfig({
  plugins: [viteSingleFile()],
  build: {
    // Clean only generated output; the Python package also ships hand-written assets.
    outDir: fileURLToPath(new URL("./dist", import.meta.url)),
    emptyOutDir: true,
    rollupOptions: {
      input: fileURLToPath(new URL("./query-result.html", import.meta.url)),
    },
  },
});
