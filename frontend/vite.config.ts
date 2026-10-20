import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Caddy serves the built files and proxies /api to FastAPI in production.
// In development Vite proxies instead, so the cookie is same-origin either way
// and nothing needs CORS.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { '/api': 'http://127.0.0.1:8000' } },
  build: { outDir: 'dist', sourcemap: false },
})
