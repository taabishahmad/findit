# FindIt v2 – Setup Guide

## STEP 1: Database
1. Start XAMPP → Apache + MySQL
2. Go to http://localhost/phpmyadmin
3. Click SQL tab → paste entire findit_db.sql → Go

## STEP 2: Install packages
    pip install -r requirements.txt



## Admin Panel
URL:      http://127.0.0.1:5000/admin
Username: admin  |  Password: admin123

## Features
- Register with Gmail OTP verification (must be real email)
- Bcrypt hashed passwords in database
- Login/Logout/Forgot Password with OTP reset
- Post Lost or Found items (login required)
- Only original poster OR admin can mark resolved
- WhatsApp + SMS direct message buttons on every post
- AI Chatbot (OpenAI GPT-3.5 with rule-based fallback)
- AI Description Suggester on Post form
- Dark/Light mode toggle (saved in browser)
- Back buttons on every page
- Admin: post management + user management
- Responsive mobile layout
