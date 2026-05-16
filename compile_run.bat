@echo off
chcp 65001 >nul
cd /d "%~dp0"

if "%~1"=="" (
    echo 用法: compile_run.bat 文件.za
    echo 示例: compile_run.bat demo.za
    pause
    exit /b 1
)

set "INPUT=%~1"
set "OUTPUT=%~n1.zab"

echo [1] 编译 %INPUT% ...
python -X utf8 -m zhiai compiler/main.za "%INPUT%" -o "%OUTPUT%"
if %errorlevel% neq 0 (
    echo 编译失败
    pause
    exit /b 1
)

echo [2] 执行 %OUTPUT% ...
echo ----------------------------------------
python -X utf8 zhiai/vm.py "%OUTPUT%"
echo ----------------------------------------
echo 完成！字节码文件: %OUTPUT%
pause
