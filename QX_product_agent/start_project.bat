@echo off
title QX Agent 启动器
chcp 65001 >nul 2>&1

echo ============================================================
echo   QX Product Research Agent — 全模块一键启动
echo ============================================================
echo.
echo 正在通过 WSL 启动全部服务 (WSL 原生文件系统)...
echo.

wsl --status >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] WSL 未安装或未启用，请先安装 WSL2 Ubuntu
    pause
    exit /b 1
)

wsl -e bash /home/administrator/dev/agents/QX_product_agent/start_all.sh
if %errorlevel% neq 0 (
    echo.
    echo [警告] 部分服务可能启动失败，请检查上方日志
)

echo.
pause
