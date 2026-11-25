@echo off
cd /d "%~dp0"
python -m streamlit run local_event_app.py --server.address 0.0.0.0 --server.port 8501
pause
