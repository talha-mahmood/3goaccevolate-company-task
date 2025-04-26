@echo off
echo Installing Playwright and browser dependencies...
pip install playwright
python -m playwright install chromium

echo Installation complete! Playwright is now ready to use.
pause
