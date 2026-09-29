/* Deliberately separate from vite.config.ts, not merged via `vitest/
   config`'s defineConfig there — vitest bundles its own nested copy of
   Vite, and its types don't structurally match this app's own `vite`
   dependency closely enough for `tsc -b` (npm run build) to type-check
   vite.config.ts if the two are combined. Keeping them apart means
   vite.config.ts is only ever type-checked against this app's own Vite,
   and this file (not in tsconfig.node.json's "include") never is. */
import { defineConfig, mergeConfig } from "vitest/config"
import viteConfig from "./vite.config"

export default mergeConfig(viteConfig, defineConfig({
  test: {
    environment: "jsdom",
    setupFiles: "./src/setupTests.ts",
    globals: true,
  },
}))
