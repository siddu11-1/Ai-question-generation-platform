# 🚀 Deployment Guide — AI Question System

## Option A — Run Locally (Your Computer)

### 1. Install MySQL
Download: https://dev.mysql.com/downloads/mysql/
Remember your root password.

### 2. Create Database
```sql
mysql -u root -p
CREATE DATABASE ai_question_db CHARACTER SET utf8mb4;
EXIT;
```

### 3. Set Up .env
Copy `.env.example` → `.env` and fill in:
```
GEMINI_API_KEY=AIzaSy...
DB_HOST=localhost
DB_PORT=3306
DB_NAME=ai_question_db
DB_USER=root
DB_PASSWORD=your_password
```

### 4. Install & Run
```bash
pip install -r requirements.txt
streamlit run app.py
```
App runs at: http://localhost:8501

---

## Option B — Deploy to Cloud (Students Access Without Localhost)

### 🌐 Railway.app (Recommended — Free tier available)

1. Create account: https://railway.app
2. New Project → Deploy from GitHub
3. Add MySQL plugin (free)
4. Set environment variables in Railway dashboard:
   - GEMINI_API_KEY, DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
5. Railway gives you a public URL like: https://your-app.up.railway.app
6. Set APP_BASE_URL=https://your-app.up.railway.app in Railway env vars
7. Share exam links — students open them directly in browser!

### 🌐 Streamlit Cloud (Free)

1. Push code to GitHub (remove real credentials first)
2. Go to: https://streamlit.io/cloud
3. Connect GitHub repo → select app.py
4. Add secrets in Streamlit Cloud dashboard:
   ```toml
   [mysql]
   host = "your-mysql-host.com"
   port = 3306
   database = "ai_question_db"
   user = "your_user"
   password = "your_password"

   [gemini]
   api_key = "AIzaSy..."
   ```
5. Get public URL like: https://yourapp.streamlit.app
6. Exam links work directly in browser for all students!

### 🌐 Render.com (Free tier)
Similar to Railway — create Web Service, add PostgreSQL or MySQL addon.

---

## Default Login Accounts
| Role    | Username | Password    |
|---------|----------|-------------|
| Admin   | admin    | admin123    |
| Trainer | trainer  | trainer123  |
| Student | student  | student123  |

---

## How Exam Links Work (Without Localhost)

1. Trainer creates exam link → gets URL like `https://your-app.up.railway.app/?exam_token=abc123`
2. Trainer shares URL via WhatsApp/email/Google Classroom
3. Student opens URL in Chrome/any browser
4. Student sees **Login** or **Request Access** options
5. If new: enters Name + Roll Number → submits request
6. Trainer sees 🆕 NEW USER or 🟡 EXISTING USER badge in dashboard
7. Trainer clicks Approve → student gets credentials
8. Student logs in → takes exam → result emailed automatically

---

## What's Stored in MySQL (Live)

| When...                    | MySQL stores...                          |
|---------------------------|------------------------------------------|
| Student registers         | users table (name, email, roll, password)|
| Trainer creates bank      | question_banks table                     |
| Gemini generates question | questions table (instant)                |
| Student takes exam        | exam_sessions + exam_answers (live)      |
| Student submits answer    | exam_answers table                       |
| Student passes            | star_ratings computed + stored           |
| Admin schedules email     | result_schedules table                   |
