import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  // P0.6 拆包：vendor 三组分包（react 生态 / 图表编辑器重件 / 其余），
  // 消除 2MB 单 chunk；编辑器页已 React.lazy 路由级分包
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined
          if (id.includes('echarts') || id.includes('zrender')) return 'vendor-echarts'
          if (id.includes('prosemirror') || id.includes('codemirror')) return 'vendor-prose'
          if (/node_modules\/(react|react-dom|scheduler|react-[^/]+|use-sync-external-store)\//.test(id)
            || id.includes('redux') || id.includes('immer')) return 'vendor-react'
          if (id.includes('pptx') || id.includes('jszip') || id.includes('lucide')
            || id.includes('dnd') || id.includes('html2canvas') || id.includes('jspdf')
            || id.includes('grapesjs')) return 'vendor-editor'
          if (id.includes('recharts') || id.includes('d3-') || id.includes('victory-vendor')) {
            return 'vendor-charts'
          }
          return 'vendor-misc'
        },
      },
    },
  },
  server: {
    port: 5173,
    host: true,
    // Cloudflare tunnel 公网域名放行（下游手工使用场景）
    allowedHosts: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
