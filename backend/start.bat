@echo off
echo ============================================
echo  BillFlow Pro — Setup and Run
echo ============================================

echo.
echo [1/2] Installing Python packages...
pip install flask flask-sqlalchemy flask-login flask-mail flask-wtf flask-migrate flask-cors python-dotenv werkzeug sqlalchemy num2words openpyxl pyjwt bleach cloudinary

echo.
echo [2/2] Starting BillFlow Pro...
echo  Open your browser: http://localhost:5000
echo  Register your first company account!
echo.

cd /d %~dp0
python app.py

pause
