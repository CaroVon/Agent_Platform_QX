import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { App } from './App'
import './styles/globals.css'

/**
 * ============================================================
 * React Query 配置
 *
 * 关键配置说明：
 * - staleTime: 数据保持"新鲜"的时间。设置为 5s 意味着
 *   5s 内多次请求同一 key 不会触发网络请求。
 * - gcTime (原 cacheTime): 不活动的缓存保留时间。
 * - refetchOnWindowFocus: 切回 Tab 时是否重新请求。
 * ============================================================
 */
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5_000,
      gcTime: 5 * 60 * 1000,
      retry: 2,
      refetchOnWindowFocus: false,
    },
  },
})

const rootElement = document.getElementById('root')
if (!rootElement) throw new Error('Root element not found')

ReactDOM.createRoot(rootElement).render(
  <React.StrictMode>
    <BrowserRouter>
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>
    </BrowserRouter>
  </React.StrictMode>,
)
