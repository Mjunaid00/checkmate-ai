import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import { copyFileSync, existsSync } from 'node:fs'
import { join } from 'node:path'

// GitHub Pages (like any static host without SPA rewrites) answers unknown
// paths with 404.html. A copy of index.html there lets BrowserRouter handle a
// page refresh or a deep link such as /login.
function spaFallback() {
  let outDir = 'dist'
  let root = process.cwd()
  return {
    name: 'checkmate-spa-404-fallback',
    apply: 'build',
    configResolved(config) {
      outDir = config.build.outDir
      root = config.root
    },
    closeBundle() {
      const index = join(root, outDir, 'index.html')
      if (existsSync(index)) copyFileSync(index, join(root, outDir, '404.html'))
    },
  }
}

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_')
  // '/' for the dev server and root deployments; '/<repo>/' for a GitHub Pages
  // project site (set by .github/workflows/deploy-pages.yml).
  const base = process.env.VITE_BASE_PATH || env.VITE_BASE_PATH || '/'
  return {
    base,
    plugins: [react(), spaFallback()],
    server: {
      port: 5173,
      // The backend only allows CORS from localhost:5173. Without strictPort,
      // Vite silently moves to 5174 when the port is busy and every API call fails.
      strictPort: true,
    },
  }
})
