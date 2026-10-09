@echo off
cd /d "d:\New folder (7)\billflow-pro"
python test_startup.py > output.log 2>&1
echo Done >> output.log
