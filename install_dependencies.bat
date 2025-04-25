@echo off
echo Installing dependencies...
echo.

REM Update pip first
python -m pip install --upgrade pip

REM Install binary wheels for problematic packages first
echo Installing binary packages...
pip install --only-binary=:all: aiohttp lxml

REM Install the rest of the requirements
echo Installing remaining requirements...
pip install -r requirements.txt --no-deps --ignore-installed aiohttp lxml

echo.
echo Dependencies installed successfully!
