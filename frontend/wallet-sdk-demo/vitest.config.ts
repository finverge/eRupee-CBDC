/* Deliberately separate from vite.config.ts — see agent-app/vitest.
   config.ts's comment for why (vitest's nested Vite copy breaks tsc -b's
   type-check of vite.config.ts if merged there directly). Also carries
   two test-only fixes this app specifically needs, since it imports
   ../../sdk/wallet-sdk/src (outside this app's own root):
   - esbuild.jsx: sdk/wallet-sdk has no tsconfig.json of its own, so
     esbuild's per-file "nearest tsconfig" lookup for JSX settings can
     miss this app's tsconfig.app.json (jsx: "react-jsx") for files under
     that directory, falling back to the classic transform that expects a
     global `React` in scope — "React is not defined" at render time. A
     production `vite build` never hits this (it never executes hooks),
     only rendering during tests does.
   - resolve.dedupe: sdk/wallet-sdk has its own node_modules/react (added
     only so tsc can type-check it in isolation — see its package.json).
     Without dedupe, Vite resolves two separate React copies for one
     component tree, which throws "Invalid hook call" the moment a
     component actually renders. */
import { defineConfig, mergeConfig } from "vitest/config"
import viteConfig from "./vite.config"

export default mergeConfig(viteConfig, defineConfig({
  esbuild: {
    jsx: "automatic",
  },
  resolve: {
    dedupe: ["react", "react-dom"],
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/setupTests.ts",
    globals: true,
  },
}))
