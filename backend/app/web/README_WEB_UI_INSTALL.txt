Install steps (Windows):

1) Replace:
   C:\BYP_Ops_System\backend\app\main.py

2) Create folder (if missing):
   C:\BYP_Ops_System\backend\app\web\

3) Put these files into app\web\:
   index.html
   app.js

4) Start server:
   python -m uvicorn app.main:app --reload

5) Open:
   http://127.0.0.1:8000/
