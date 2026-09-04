@echo off
chcp 65001 > nul

:: =========================================
:: 新增功能：复制配置文件到目标路径
:: =========================================
echo.
echo [*] 正在复制配置文件...
set "SRC_DIR=C:\Users\MX\Desktop\MAA\MaaAssistantArknights\build\bin\Release\config"
set "DST_DIR=C:\Users\MX\Desktop\MAA"

:: 检查源路径是否存在
if exist "%SRC_DIR%" (
    :: 使用 xcopy 复制文件，/e 表示包含所有子目录，/y 表示覆盖同名文件，/i 表示如果目标不存在则自动创建
    xcopy "%SRC_DIR%\*" "%DST_DIR%\" /e /y /i > nul
    echo [*] 配置文件复制完成！
) else (
    echo [警告] 未找到源配置目录: %SRC_DIR%
    echo [*] 跳过复制，继续执行后续步骤...
)

:: 1. 进入项目路径
cd /d "C:\Users\MX\Desktop\MAA\MaaAssistantArknights"

echo.
echo =========================================
echo       开始自动同步 MAA 官方最新代码
echo =========================================

echo.
echo [0/6] 开启 Sing-box 代理 (端口: 20122)...
git config --global http.proxy http://127.0.0.1:20122
git config --global https.proxy http://127.0.0.1:20122

echo.
echo [1/6] 正在拉取官方 origin 远程仓库最新变动...
git fetch origin
if %errorlevel% neq 0 goto ERROR

echo.
echo [2/6] 切换至免弹窗分支 no-popup...
git checkout no-popup
if %errorlevel% neq 0 goto ERROR

echo.
echo [3/6] 合并官方 dev-v2 代码到 no-popup (自动提交不弹窗)...
git merge origin/dev-v2 --no-edit
if %errorlevel% neq 0 goto ERROR

echo.
echo [4/6] 推送更新后的 no-popup 到你的 GitHub (myfork)...
git push myfork no-popup
if %errorlevel% neq 0 goto ERROR

echo.
echo [5/6] 同步本地与 GitHub 的 dev-v2 分支 (自动提交不弹窗)...
git checkout dev-v2 || goto ERROR
git merge origin/dev-v2 --no-edit || goto ERROR
git push myfork dev-v2 || goto ERROR

echo.
echo [6/6] 切换回工作分支 no-popup...
git checkout no-popup
if %errorlevel% neq 0 goto ERROR

echo.
echo [*] 清理 Git 代理配置，恢复默认...
git config --global --unset http.proxy
git config --global --unset https.proxy

echo.
echo =========================================
echo       更新完成！现在可以去 VS 重新编译了
echo =========================================
pause
exit /b 0

:ERROR
echo.
echo [*] 清理 Git 代理配置，恢复默认...
git config --global --unset http.proxy
git config --global --unset https.proxy
echo.
echo =========================================
echo   [错误] 某一步骤执行失败/发生冲突！
echo   请检查上方报错提示（如网络问题或冲突）
echo =========================================
pause
exit /b 1