@echo off
setlocal enabledelayedexpansion

:: 检查ffmpeg是否可用
where ffmpeg >nul 2>&1
if %errorlevel% neq 0 (
    echo 错误：未找到ffmpeg，请先安装ffmpeg并添加到系统路径
    echo 访问 https://ffmpeg.org/download.html 下载
    pause
    exit /b 1
)

:: 设置音量倍数（默认3.0=300%）
set VOLUME_MULTIPLIER=10.0

echo 正在处理目录: %cd%
echo 音量放大倍数: %VOLUME_MULTIPLIER%

:: 遍历所有WAV文件
for %%F in (*.wav) do (
    echo 正在处理: "%%F"
    
    :: 生成临时文件名（避免覆盖原文件）
    set "tempfile=%%~nF_temp%%~xF"
    
    :: 使用ffmpeg增大音量
    ffmpeg -hide_banner -loglevel error -i "%%F" -af "volume=%VOLUME_MULTIPLIER%" "!tempfile!"
    
    :: 替换原始文件
    if exist "!tempfile!" (
        del "%%F"
        ren "!tempfile!" "%%~nxF"
        echo 已更新: "%%F"
    ) else (
        echo 错误处理文件: "%%F"
    )
)

echo 处理完成！
pause