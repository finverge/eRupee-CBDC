/* Deliberately separate from vite.config.ts — see agent-app/vitest.
   config.ts's comment for why (vitest's nested Vite copy breaks tsc -b's
   type-check of vite.config.ts if merged there directly). */
import { defineConfig, mergeConfig } from "vitest/config"
import viteConfig from "./vite.config"

export default mergeConfig(viteConfig, defineConfig({
  test: {
    environment: "jsdom",
    setupFiles: "./src/setupTests.ts",
    globals: true,
  },
}))
