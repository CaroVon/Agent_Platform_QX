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
  // P0.6 拆包 v2：按需大件独立分组 + 其余 node_modules 归单一 vendor。
  // 教训：vendor-react/vendor-misc 两分法曾因跨组循环依赖（Circular chunk 警告）
  // 导致 React 未初始化（createContext undefined）→ 公网页面全黑；
  // 单一 vendor 组内部无法成环，大件组均为叶子依赖（无反向 import 应用代码）。
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined
          if (id.includes('echarts') || id.includes('zrender')) return 'vendor-echarts'
          if (id.includes('prosemirror') || id.includes('codemirror')) return 'vendor-prose'
          if (id.includes('recharts') || id.includes('d3-') || id.includes('victory-vendor')) {
            return 'vendor-charts'
          }
          if (id.includes('pptx') || id.includes('jszip')
            || id.includes('dnd') || id.includes('html2canvas') || id.includes('jspdf')
            || id.includes('grapesjs')) return 'vendor-editor'
          return 'vendor'
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
