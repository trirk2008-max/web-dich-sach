@echo off
title He Thong Dich Sach & Tai Lieu Dai
echo ========================================================
echo        DICH SACH & TAI LIEU DAI - FULL TIENG VIET
echo ========================================================
echo Dang khoi dong may chu web tai http://localhost:5000 ...
start http://localhost:5000
python -m uvicorn app:app --host 0.0.0.0 --port 5000 --reload
pause
