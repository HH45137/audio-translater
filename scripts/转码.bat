@echo off
setlocal enabledelayedexpansion

:: 检查FFmpeg是否安装
where ffmpeg >nul 2>&1
if %errorlevel% neq 0 (
    echo 错误：未检测到FFmpeg，请先安装FFmpeg并将其添加到系统路径
    echo 访问 https://ffmpeg.org/download.html 下载
    pause
    exit /b 1
)

:: 创建临时文件夹
set "tempDir=temp_44k"
if not exist "%tempDir%" mkdir "%tempDir%"

:: 转换所有WAV文件
set converted=0
for %%f in (*.wav) do (
    echo 正在处理: "%%f"
    ffmpeg -loglevel warning -i "%%f" -ar 44100 -acodec pcm_s16le "%tempDir%\%%~nf_temp.wav"
    
    if !errorlevel! equ 0 (
        move /y "%tempDir%\%%~nf_temp.wav" "%%f" >nul
        set /a converted+=1
        echo [成功] 已转换: "%%f"
    ) else (
        echo [失败] 转换出错: "%%f"
    )
)

:: 清理临时文件夹
rd /s /q "%tempDir%" 2>nul

echo.
echo ========================
echo 转换完成！共成功转换 !converted! 个文件
pause