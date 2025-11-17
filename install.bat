@echo off
chcp 65001
echo ========================================
echo    تثبيت البوت التلقائي - Windows
echo ========================================

echo 🔧 جاري التحقق من Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python غير مثبت على النظام
    echo 📥 يرجى تحميل Python من python.org
    pause
    exit /b 1
)

echo ✅ Python مثبت

echo.
echo 📦 جاري تثبيت المكتبات...
python -m pip install --upgrade pip
python -m pip install pyTelegramBotAPI yt-dlp requests pillow

echo.
echo 🎵 جاري تثبيت FFmpeg...
python bot.py

echo.
echo ✅ تم التثبيت بنجاح!
echo 🚀 جاري تشغيل البوت...
echo.

pause