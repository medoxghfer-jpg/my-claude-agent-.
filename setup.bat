@echo off
chcp 65001 >nul
echo.
echo Get a free key from: https://aistudio.google.com/apikey
echo.
set /p "KEY=Paste your Gemini API key here, then press Enter: "
if "%KEY%"=="" (
  echo No key entered. Run setup.bat again.
  pause
  exit /b
)
> .env echo GEMINI_API_KEY=%KEY%
>> .env echo ANTHROPIC_API_KEY=
>> .env echo AI_MODEL=
echo.
echo Done! The .env file was created. Now run run.bat
pause
