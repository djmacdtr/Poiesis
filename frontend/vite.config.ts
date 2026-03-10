import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

const apiProxyTarget = process.env.VITE_API_PROXY_TARGET ?? 'http://127.0.0.1:18000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': {
        target: apiProxyTarget,
        changeOrigin: true,
      },
      '/health': {
        target: apiProxyTarget,
        changeOrigin: true,
      },
      '/openapi.json': {
        target: apiProxyTarget,
        changeOrigin: true,
      },
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          // 将图表依赖独立拆包，避免首屏为统计页支付过高下载成本。
          if (id.includes('recharts')) {
            return 'charts'
          }
          // React 栈与路由独立成基础包，便于长期缓存。
          if (
            id.includes('react/') ||
            id.includes('react-dom/') ||
            id.includes('react-router') ||
            id.includes('@tanstack/react-query')
          ) {
            return 'framework'
          }
          // 图标库体积不算特别大，但拆出去可进一步缩小主入口 chunk。
          if (id.includes('lucide-react')) {
            return 'icons'
          }
        },
      },
    },
  },
})
