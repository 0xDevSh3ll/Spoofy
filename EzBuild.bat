@echo off
pip install -r requirements.txt
pyinstaller --onefile --noconsole --icon=Source/icon.ico Source/spoofly.py --name Spoofly
