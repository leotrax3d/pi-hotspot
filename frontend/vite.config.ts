import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { '@': path.resolve(import.meta.dirname, './src') } },
  base: '/static/app/',
  build: { rollupOptions: { input: { admin: path.resolve(import.meta.dirname, 'index.html'), community: path.resolve(import.meta.dirname, 'community.html') } } },
})
