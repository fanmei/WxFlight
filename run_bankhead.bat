@echo off
call conda activate wxflight
python wxflight_core.py --site bankhead --hour 12
pause
