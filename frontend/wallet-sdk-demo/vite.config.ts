import path from "path"
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@sdk": path.resolve(import.meta.dirname, "../../sdk/wallet-sdk/src"),
    },
  },
})
