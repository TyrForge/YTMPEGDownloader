@echo off

pip install -r requirements.txt
pyinstaller --noconfirm --onefile --windowed --icon "./src/FILE.ico" --name "YT2MPEG" "./src/main.py"

Print "Cleaning up..."
rmdir /S /Q "./build/"
DEL YT2MPEG.spec

cls
color a
echo --------------DONE--------------
echo EXE CAN BE FOUND FROM DIST FOLDER

pause

