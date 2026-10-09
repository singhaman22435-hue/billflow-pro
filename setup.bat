@echo off
echo ==============================================
echo BillFlow Pro - Node.js + React Migration Setup
echo ==============================================

echo [1/2] Setting up Backend API (Node.js)
mkdir server
cd server
call npm init -y
call npm install express cors dotenv jsonwebtoken bcryptjs multer
call npm install -D prisma nodemon
call npx prisma init --datasource-provider sqlite
cd ..

echo [2/2] Setting up Frontend (React + Vite)
call npm create vite@latest client -- --template react
cd client
call npm install
call npm install react-router-dom axios tailwindcss postcss autoprefixer recharts
call npx tailwindcss init -p
cd ..

echo ==============================================
echo Setup Complete! 
echo Please restart your terminal if needed.
echo ==============================================
pause
