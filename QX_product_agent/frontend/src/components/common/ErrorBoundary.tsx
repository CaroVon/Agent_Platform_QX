/**
 * 全局错误边界 —— 防止单页异常导致整站白屏
 */
import React from 'react'

interface Props {
  children: React.ReactNode
}

interface State {
  hasError: boolean
  message: string
}

export class ErrorBoundary extends React.Component<Props, State> {
  state: State = { hasError: false, message: '' }

  static getDerivedStateFromError(error: unknown): State {
    return {
      hasError: true,
      message: error instanceof Error ? error.message : String(error),
    }
  }

  componentDidCatch(error: unknown, info: React.ErrorInfo) {
    console.error('[ErrorBoundary]', error, info.componentStack)
  }

  handleReload = () => {
    this.setState({ hasError: false, message: '' })
    window.location.reload()
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: '#F7F5F0',
          fontFamily: 'system-ui, sans-serif',
        }}>
          <div style={{ maxWidth: 420, textAlign: 'center', padding: 32 }}>
            <div style={{ fontSize: 40, marginBottom: 12 }}>⚠️</div>
            <h1 style={{ fontSize: 18, fontWeight: 600, color: '#24415E', marginBottom: 8 }}>
              页面渲染出错
            </h1>
            <p style={{ fontSize: 13, color: '#6B7280', marginBottom: 20, wordBreak: 'break-all' }}>
              {this.state.message || '发生未知错误'}
            </p>
            <button
              onClick={this.handleReload}
              style={{
                background: '#24415E',
                color: '#fff',
                border: 'none',
                borderRadius: 8,
                padding: '10px 24px',
                fontSize: 14,
                cursor: 'pointer',
              }}
            >
              重新加载
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
