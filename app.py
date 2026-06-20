from flask import (Flask, render_template, request, redirect, url_for,
                   session, flash, jsonify)
import pymysql, os, re, csv, random, string, json
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from functools import wraps
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import urllib.request, urllib.parse
from dotenv import load_dotenv
load_dotenv()

# ══════════════════════════════════════════════════════════════
#  APP CONFIG
# ══════════════════════════════════════════════════════════════
app = Flask(__name__)
app.secret_key = 'findit_v2_ultra_secret_2026_iiui'

UPLOAD_FOLDER      = os.path.join('static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
app.config['UPLOAD_FOLDER']      = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

MAIL_SERVER   = 'smtp.gmail.com'
MAIL_PORT     = 587
MAIL_USERNAME = os.environ.get('MAIL_USERNAME', 'tabish.bscs4969@student.iiu.edu.pk')
MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', 'kbnp onbn ffsa phyy')
MAIL_FROM     = f'FindIt <{MAIL_USERNAME}>'

OPENAI_API_KEY = os.environ.get('GROQ_API_KEY', '')

# ══════════════════════════════════════════════════════════════
#  DATABASE
# ══════════════════════════════════════════════════════════════
def get_db():
    return pymysql.connect(
        host=os.environ.get('MYSQLHOST', 'localhost'),
        user=os.environ.get('MYSQLUSER', 'root'),
        password=os.environ.get('MYSQLPASSWORD', ''),
        database=os.environ.get('MYSQLDATABASE', 'findit_db'),
        port=int(os.environ.get('MYSQLPORT', 3306)),
        cursorclass=pymysql.cursors.DictCursor
    )

def allowed_file(fn):
    return '.' in fn and fn.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ══════════════════════════════════════════════════════════════
#  AUTH DECORATORS
# ══════════════════════════════════════════════════════════════
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            flash('Please log in first.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated

# ══════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════
def generate_otp(length=6):
    return ''.join(random.choices(string.digits, k=length))

def is_valid_email(email):
    pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    return bool(re.match(pattern, email.strip()))

def is_iiui_email(email):
    pattern = r'^[a-zA-Z]+\.[a-zA-Z]+[0-9]{1,5}@student\.iiu\.edu\.pk$'
    return bool(re.match(pattern, email.strip().lower()))

def is_valid_phone(phone):
    cleaned = re.sub(r'[\s\-]', '', phone)
    return bool(re.match(r'^(\+92|0)3[0-9]{9}$', cleaned))

def send_otp_email(to_email, otp, purpose='verify'):
    """
    Sends OTP email synchronously.
    Returns True if sent successfully, False if failed.
    """
    try:
        subject = "FindIt – Your OTP Code"
        if purpose == 'reset':
            subject = "FindIt – Password Reset OTP"

        html_body = f"""
        <div style="font-family:Arial,sans-serif;max-width:480px;margin:auto;background:#f8fafa;
                    border-radius:14px;overflow:hidden;border:1px solid #d0e8e8;">
          <div style="background:#0d7377;padding:24px;text-align:center;">
            <h1 style="color:#fff;margin:0;font-size:28px;">FindIt</h1>
            <p style="color:rgba(255,255,255,.8);margin:4px 0 0;">Community Lost &amp; Found Board</p>
          </div>
          <div style="padding:32px 28px;">
            <h2 style="color:#0a5c60;margin-top:0;">
              {'Verify your email' if purpose=='verify' else 'Reset your password'}
            </h2>
            <p style="color:#333;font-size:15px;">Your One-Time Password (OTP) is:</p>
            <div style="background:#0d7377;color:#fff;font-size:36px;font-weight:bold;
                        letter-spacing:10px;text-align:center;padding:20px;border-radius:10px;
                        margin:16px 0;">{otp}</div>
            <p style="color:#666;font-size:13px;">This OTP expires in <strong>10 minutes</strong>.
               Do not share it with anyone.</p>
            <p style="color:#666;font-size:13px;margin-top:20px;">
              If you did not request this, please ignore this email.
            </p>
          </div>
          <div style="background:#e6f7f7;padding:16px;text-align:center;
                      color:#5a7a7b;font-size:12px;">
            &copy; 2026 FindIt – IIUI Web Engineering Project
          </div>
        </div>
        """
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From']    = MAIL_FROM
        msg['To']      = to_email
        msg.attach(MIMEText(html_body, 'html'))

        with smtplib.SMTP(MAIL_SERVER, MAIL_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(MAIL_USERNAME, MAIL_PASSWORD)
            server.sendmail(MAIL_USERNAME, to_email, msg.as_string())
        print(f"[Email OK] OTP sent to {to_email}")
        return True
    except Exception as e:
        print(f"[Email FAILED] {e}")
        return False

def store_otp(email, purpose='verify'):
    otp    = generate_otp()
    expiry = datetime.now() + timedelta(minutes=10)
    db  = get_db()
    cur = db.cursor()
    cur.execute("UPDATE otp_tokens SET used=1 WHERE email=%s AND purpose=%s", (email, purpose))
    cur.execute(
        "INSERT INTO otp_tokens (email, otp, purpose, expires_at) VALUES (%s,%s,%s,%s)",
        (email, otp, purpose, expiry)
    )
    db.commit()
    db.close()
    return otp

def verify_otp_code(email, code, purpose='verify'):
    db  = get_db()
    cur = db.cursor()
    cur.execute(
        """SELECT id FROM otp_tokens
           WHERE email=%s AND otp=%s AND purpose=%s AND used=0
             AND expires_at > NOW()
           ORDER BY id DESC LIMIT 1""",
        (email, code, purpose)
    )
    row = cur.fetchone()
    if row:
        cur.execute("UPDATE otp_tokens SET used=1 WHERE id=%s", (row['id'],))
        db.commit()
    db.close()
    return bool(row)

# ══════════════════════════════════════════════════════════════
#  AI HELPERS
# ══════════════════════════════════════════════════════════════
def load_items_context():
    ctx = []
    csv_path = os.path.join('data', 'items.csv')
    if os.path.exists(csv_path):
        with open(csv_path, newline='', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                ctx.append(f"- {row['item']} ({row['category']}): {row['tips']}")
    return '\n'.join(ctx)

def get_active_posts_summary():
    try:
        db  = get_db()
        cur = db.cursor()
        cur.execute(
            "SELECT title, type, location, date_lost FROM posts "
            "WHERE status='active' ORDER BY created_at DESC LIMIT 20"
        )
        rows = cur.fetchall()
        db.close()
        lines = []
        for r in rows:
            d = r['date_lost'].strftime('%b %d') if r['date_lost'] else 'unknown date'
            lines.append(f"- [{r['type'].upper()}] {r['title']} at {r['location']} ({d})")
        return '\n'.join(lines) if lines else 'No active posts currently.'
    except:
        return 'Unable to fetch posts.'

def call_anthropic(messages_list, system_prompt):
    """Groq Llama3-8b — free API. Key from https://console.groq.com"""
    try:
        payload = json.dumps({
            "model": "llama3-8b-8192",
            "max_tokens": 500,
            "temperature": 0.7,
            "messages": [{"role": "system", "content": system_prompt}] + messages_list
        }).encode('utf-8')
        req = urllib.request.Request(
            'https://api.groq.com/openai/v1/chat/completions',
            data=payload,
            headers={
                'Content-Type':  'application/json',
                'Authorization': f'Bearer {OPENAI_API_KEY}'
            },
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            reply = data['choices'][0]['message']['content']
            print(f"[Groq OK] reply length: {len(reply)}")
            return reply
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"[Groq HTTP Error {e.code}]: {body}")
        return None
    except urllib.error.URLError as e:
        print(f"[Groq URL Error]: {e.reason}")
        return None
    except Exception as e:
        print(f"[Groq Error]: {type(e).__name__}: {e}")
        return None

def smart_fallback(user_msg, posts_ctx):
    """Smart fallback when Groq API is unavailable."""
    ul = user_msg.lower().strip()
    common_items = ['wallet', 'phone', 'mobile', 'laptop', 'bag', 'keys', 'id',
                    'card', 'earphone', 'charger', 'bottle', 'glasses', 'watch',
                    'jacket', 'shoes']
    locations = ['cafe', 'cafeteria', 'library', 'block', 'parking', 'mosque',
                 'class', 'classroom', 'lab', 'gate', 'hostel', 'gym']
    mentioned_item = next((i for i in common_items if i in ul), None)
    mentioned_loc  = next((l for l in locations if l in ul), None)

    is_question = any(w in ul for w in ['did you', 'did anyone', 'has anyone', 'who found',
                                         'who lost', 'can you see', 'do you see', 'see something',
                                         'is there', 'any post', 'check'])
    is_lost  = any(w in ul for w in ['i lost', 'i have lost', 'lost my', 'missing',
                                      "can't find", 'i misplaced', 'dropped'])
    is_found = any(w in ul for w in ['i found', 'i have found', 'found a', 'picked up',
                                      'i put', 'i have put', 'i posted', 'i placed'])
    is_how   = any(w in ul for w in ['how', 'guide', 'help me', 'what should', 'what do'])

    if is_question and mentioned_item:
        if mentioned_item.lower() in posts_ctx.lower():
            return (f"Yes! I can see a post about a {mentioned_item} on the FindIt board. "
                    f"Go to the main board and search '{mentioned_item}' to see full details "
                    f"and contact the poster directly via WhatsApp.")
        else:
            return (f"I don't see a current post about a {mentioned_item} on the board. "
                    f"Post it as lost/found so others can see it. "
                    f"Also check the security office — they hold found items daily.")
    elif is_found:
        item_text = f"the {mentioned_item}" if mentioned_item else "the item"
        loc_text  = f"near the {mentioned_loc}" if mentioned_loc else "on campus"
        return (f"Great! Post {item_text} as 'Found' on FindIt — click '+ Post Item', "
                f"select Found, describe where you found it {loc_text}, "
                f"and add your contact. The owner will WhatsApp you directly.")
    elif is_lost:
        item_text = f"your {mentioned_item}" if mentioned_item else "your item"
        return (f"Post {item_text} on FindIt immediately with a photo and description. "
                f"Also check the board — someone may have already posted it as found. "
                f"Visit the security office too — they collect found items daily.")
    elif mentioned_item:
        return (f"Are you asking about a {mentioned_item}? Tell me if you lost it or found it "
                f"and I'll guide you. You can also search '{mentioned_item}' on the board.")
    elif is_how:
        return ("Register with your IIUI email, verify via OTP, then click '+ Post Item'. "
                "Choose Lost or Found, fill details with a photo, and submit. "
                "Others can contact you directly via WhatsApp!")
    else:
        return ("I'm FindIt Assistant. Tell me what you lost or found, "
                "or ask me to check the board for a specific item!")

# ══════════════════════════════════════════════════════════════
#  AUTH ROUTES
# ══════════════════════════════════════════════════════════════
@app.route('/register', methods=['GET', 'POST'])
def register():
    if session.get('user_id'):
        return redirect(url_for('index'))

    if request.method == 'POST':
        name     = request.form.get('name', '').strip()
        email    = request.form.get('email', '').strip().lower()
        phone    = request.form.get('phone', '').strip()
        password = request.form.get('password', '')
        confirm  = request.form.get('confirm_password', '')

        errors = []
        if len(name) < 2:
            errors.append('Name must be at least 2 characters.')
        if not is_iiui_email(email):
            errors.append('Email must be your IIUI student email (e.g. name.bscs1234@student.iiu.edu.pk).')
        if not is_valid_phone(phone):
            errors.append('Phone must be a valid Pakistani number (e.g. 03001234567).')
        if len(password) < 8:
            errors.append('Password must be at least 8 characters long.')
        if not re.search(r'[A-Z]', password):
            errors.append('Password must contain at least one uppercase letter (A-Z).')
        if not re.search(r'[0-9]', password):
            errors.append('Password must contain at least one number (0-9).')
        if not re.search(r'[^A-Za-z0-9]', password):
            errors.append('Password must contain at least one special character (e.g. @, !, #).')
        if password != confirm:
            errors.append('Passwords do not match.')

        if errors:
            for e in errors:
                flash(e, 'error')
            return render_template('register.html', name=name, email=email, phone=phone)

        db  = get_db()
        cur = db.cursor()
        cur.execute("SELECT id FROM users WHERE email=%s", (email,))
        if cur.fetchone():
            db.close()
            flash('An account with this email already exists.', 'error')
            return render_template('register.html', name=name, email=email, phone=phone)

        pw_hash = generate_password_hash(password)
        cur.execute(
            "INSERT INTO users (name, email, phone, password_hash, is_verified) VALUES (%s,%s,%s,%s,0)",
            (name, email, phone, pw_hash)
        )
        db.commit()
        db.close()

        # Generate OTP and try to send email
        otp = store_otp(email, 'verify')
        session['pending_verify_email'] = email

        # Send email SYNCHRONOUSLY so we know if it worked
        ok = send_otp_email(email, otp, 'verify')

        if ok:
            flash('Account created! A verification OTP has been sent to your email. Please check your inbox.', 'success')
        else:
            # Email failed — this is demo/fallback mode
            flash('Account created! Email could not be delivered right now.', 'info')
            flash(f'Your OTP is: {otp} — Please use this to verify.', 'info')

        return redirect(url_for('verify_email'))

    return render_template('register.html')


@app.route('/verify-email', methods=['GET', 'POST'])
def verify_email():
    email = session.get('pending_verify_email')
    if not email:
        return redirect(url_for('register'))

    if request.method == 'POST':
        code = request.form.get('otp', '').strip()
        if verify_otp_code(email, code, 'verify'):
            db  = get_db()
            cur = db.cursor()
            cur.execute("UPDATE users SET is_verified=1 WHERE email=%s", (email,))
            db.commit()
            cur.execute("SELECT * FROM users WHERE email=%s", (email,))
            user = cur.fetchone()
            db.close()
            session.pop('pending_verify_email', None)
            session['user_id']    = user['id']
            session['user_name']  = user['name']
            session['user_email'] = user['email']
            session['user_pic']   = user.get('profile_pic') or ''
            flash(f"Welcome, {user['name']}! Your account is verified.", 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid or expired OTP. Please try again.', 'error')

    return render_template('verify_email.html', email=email)


@app.route('/resend-otp')
def resend_otp():
    email = session.get('pending_verify_email')
    if not email:
        return redirect(url_for('register'))
    otp = store_otp(email, 'verify')
    ok  = send_otp_email(email, otp, 'verify')
    if ok:
        flash('A new OTP has been sent to your email.', 'success')
    else:
        flash(f'Email failed. Your OTP is: {otp}', 'info')
    return redirect(url_for('verify_email'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('user_id'):
        return redirect(url_for('index'))

    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if not email or not password:
            flash('Please fill in all fields.', 'error')
            return render_template('login.html', email=email)

        db  = get_db()
        cur = db.cursor()
        cur.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = cur.fetchone()
        db.close()

        if not user or not check_password_hash(user['password_hash'], password):
            flash('Invalid email or password.', 'error')
            return render_template('login.html', email=email)

        if not user['is_verified']:
            session['pending_verify_email'] = email
            otp = store_otp(email, 'verify')
            ok  = send_otp_email(email, otp, 'verify')
            if ok:
                flash('Please verify your email first. A new OTP has been sent to your inbox.', 'info')
            else:
                flash(f'Please verify your email. OTP: {otp}', 'info')
            return redirect(url_for('verify_email'))

        session['user_id']    = user['id']
        session['user_name']  = user['name']
        session['user_email'] = user['email']
        session['user_pic']   = user.get('profile_pic') or ''
        flash(f"Welcome back, {user['name']}!", 'success')
        return redirect(url_for('index'))

    return render_template('login.html')


@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        db  = get_db()
        cur = db.cursor()
        cur.execute("SELECT id FROM users WHERE email=%s", (email,))
        user = cur.fetchone()
        db.close()
        if user:
            otp = store_otp(email, 'reset')
            ok  = send_otp_email(email, otp, 'reset')
            if not ok:
                flash(f'Email failed. Your OTP is: {otp}', 'info')
            else:
                flash('Password reset OTP has been sent to your email.', 'success')
        else:
            flash('If this email is registered, an OTP has been sent.', 'success')
        session['pending_reset_email'] = email
        return redirect(url_for('reset_password'))
    return render_template('forgot_password.html')


@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    email = session.get('pending_reset_email')
    if not email:
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        code     = request.form.get('otp', '').strip()
        password = request.form.get('password', '')
        confirm  = request.form.get('confirm_password', '')

        errors = []
        if len(password) < 8:
            errors.append('Password must be at least 8 characters long.')
        if not re.search(r'[A-Z]', password):
            errors.append('Password must contain at least one uppercase letter (A-Z).')
        if not re.search(r'[0-9]', password):
            errors.append('Password must contain at least one number (0-9).')
        if not re.search(r'[^A-Za-z0-9]', password):
            errors.append('Password must contain at least one special character (e.g. @, !, #).')
        if password != confirm:
            errors.append('Passwords do not match.')

        if errors:
            for e in errors:
                flash(e, 'error')
            return render_template('reset_password.html', email=email)

        if not verify_otp_code(email, code, 'reset'):
            flash('Invalid or expired OTP.', 'error')
            return render_template('reset_password.html', email=email)

        pw_hash = generate_password_hash(password)
        db  = get_db()
        cur = db.cursor()
        cur.execute("UPDATE users SET password_hash=%s WHERE email=%s", (pw_hash, email))
        db.commit()
        db.close()
        session.pop('pending_reset_email', None)
        flash('Password reset successfully! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('reset_password.html', email=email)


@app.route('/logout')
def logout():
    session.pop('user_id',    None)
    session.pop('user_name',  None)
    session.pop('user_email', None)
    flash('You have been logged out.', 'success')
    return redirect(url_for('index'))


# ══════════════════════════════════════════════════════════════
#  MAIN BOARD
# ══════════════════════════════════════════════════════════════
@app.route('/')
def index():
    search  = request.args.get('search', '').strip()
    filter_ = request.args.get('filter', 'all')
    db  = get_db()
    cur = db.cursor()
    query  = "SELECT p.*, u.name AS poster_name FROM posts p LEFT JOIN users u ON p.user_id=u.id WHERE p.status != 'resolved'"
    params = []
    if filter_ in ('lost', 'found'):
        query += " AND p.type = %s"
        params.append(filter_)
    if search:
        query += " AND (p.title LIKE %s OR p.description LIKE %s OR p.location LIKE %s)"
        like = f'%{search}%'
        params.extend([like, like, like])
    query += " ORDER BY p.created_at DESC"
    cur.execute(query, params)
    posts = cur.fetchall()
    db.close()
    return render_template('index.html', posts=posts, search=search, filter=filter_)


# ══════════════════════════════════════════════════════════════
#  POSTS
# ══════════════════════════════════════════════════════════════
@app.route('/post', methods=['GET', 'POST'])
@login_required
def post_item():
    if request.method == 'POST':
        title       = request.form['title'].strip()
        description = request.form['description'].strip()
        location    = request.form['location'].strip()
        item_type   = request.form['type']
        contact     = request.form['contact'].strip()
        date_lost   = request.form['date_lost'] or None
        if not is_valid_phone(contact):
            flash('Contact must be a valid Pakistani number (e.g. 03001234567).', 'error')
            return render_template('post.html', form=request.form)
        photo_name = None
        file = request.files.get('photo')
        if file and file.filename and allowed_file(file.filename):
            photo_name = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], photo_name))
        db  = get_db()
        cur = db.cursor()
        cur.execute(
            "INSERT INTO posts (user_id, title, description, location, type, contact, date_lost, photo, status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'active')",
            (session['user_id'], title, description, location, item_type, contact, date_lost, photo_name)
        )
        db.commit()
        db.close()
        flash('Your post has been submitted successfully!', 'success')
        return redirect(url_for('index'))
    return render_template('post.html', form={})


@app.route('/post/<int:post_id>')
def view_post(post_id):
    db  = get_db()
    cur = db.cursor()
    cur.execute(
        "SELECT p.*, u.name AS poster_name, u.email AS poster_email FROM posts p LEFT JOIN users u ON p.user_id=u.id WHERE p.id=%s",
        (post_id,)
    )
    post = cur.fetchone()
    db.close()
    if not post:
        flash('Post not found.', 'error')
        return redirect(url_for('index'))
    can_resolve = (
        session.get('admin') or
        (session.get('user_id') and session['user_id'] == post['user_id'])
    )
    return render_template('view_post.html', post=post, can_resolve=can_resolve)


@app.route('/resolve/<int:post_id>')
def resolve_post(post_id):
    db  = get_db()
    cur = db.cursor()
    cur.execute("SELECT user_id FROM posts WHERE id=%s", (post_id,))
    row = cur.fetchone()
    if not row:
        db.close()
        flash('Post not found.', 'error')
        return redirect(url_for('index'))
    is_owner = session.get('user_id') and session['user_id'] == row['user_id']
    is_admin  = session.get('admin')
    if not (is_owner or is_admin):
        db.close()
        flash('You are not authorised to resolve this post.', 'error')
        return redirect(url_for('view_post', post_id=post_id))
    cur.execute("UPDATE posts SET status='resolved' WHERE id=%s", (post_id,))
    db.commit()
    db.close()
    flash('Post marked as resolved!', 'success')
    return redirect(url_for('index'))


# ══════════════════════════════════════════════════════════════
#  AI CHATBOT
# ══════════════════════════════════════════════════════════════
@app.route('/api/chat', methods=['POST'])
def chat():
    data     = request.get_json(silent=True) or {}
    user_msg = data.get('message', '').strip()
    history  = data.get('history', [])
    if not user_msg:
        return jsonify({'error': 'Empty message'}), 400

    items_ctx = load_items_context()
    posts_ctx = get_active_posts_summary()

    system_prompt = f"""You are FindIt Assistant — a smart AI helper for FindIt, a Community Lost & Found Board at IIUI (International Islamic University Islamabad), Pakistan.

LIVE BOARD DATA — CURRENT ACTIVE POSTS:
{posts_ctx}

ITEM ADVICE BY CATEGORY:
{items_ctx}

YOUR PERSONALITY & RULES:
- You are helpful, friendly, and direct like a knowledgeable friend
- Always give a DIFFERENT, CONTEXTUAL response based on what the user actually said
- Read the conversation history carefully and respond to what was JUST said
- If someone says they posted something, acknowledge it and tell them what to expect next
- If someone mentions a specific item (wallet, phone etc), reference that specific item in your reply
- If someone mentions a location (cafe, library etc), reference that location
- Check the LIVE BOARD DATA above — if their item appears there, tell them specifically
- Keep replies to 2-3 sentences — short and helpful
- Never repeat the same response twice in a conversation
- Never start with "Hello! I'm FindIt Assistant" after the first message
- If user writes in Urdu, reply in Urdu
- Do NOT make up phone numbers or contact details
"""

    messages = []
    for h in history[-10:]:
        if h.get('role') in ('user', 'assistant') and h.get('content'):
            messages.append({'role': h['role'], 'content': h['content']})
    messages.append({'role': 'user', 'content': user_msg})

    reply = call_anthropic(messages, system_prompt)

    if not reply:
        reply = smart_fallback(user_msg, posts_ctx)

    if session.get('user_id'):
        try:
            sid = data.get('session_id', 'anon')
            db  = get_db()
            cur = db.cursor()
            cur.execute("INSERT INTO chat_history (user_id, session_id, role, message) VALUES (%s,%s,'user',%s)", (session['user_id'], sid, user_msg))
            cur.execute("INSERT INTO chat_history (user_id, session_id, role, message) VALUES (%s,%s,'assistant',%s)", (session['user_id'], sid, reply))
            db.commit()
            db.close()
        except:
            pass

    return jsonify({'reply': reply})


@app.route('/api/suggest', methods=['POST'])
@login_required
def ai_suggest():
    data  = request.get_json(silent=True) or {}
    title = data.get('title', '').strip()
    desc  = data.get('description', '').strip()
    itype = data.get('type', 'lost')
    if not title:
        return jsonify({'suggestion': ''})
    system = "You are a helpful assistant for a Lost & Found board. Given an item name and description, suggest a better, more detailed description that will help someone identify the item. Keep it under 60 words. Be specific about colour, brand, size, and identifying features."
    messages = [{'role': 'user', 'content': f"Item: {title}\nType: {itype}\nDescription: {desc}\n\nSuggest an improved description:"}]
    reply = call_anthropic(messages, system)
    return jsonify({'suggestion': reply or ''})


# ══════════════════════════════════════════════════════════════
#  ADMIN
# ══════════════════════════════════════════════════════════════
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        admin_email = os.environ.get('ADMIN_EMAIL', 'tabishahmadaiengineer@gmail.com')
        admin_pass  = os.environ.get('ADMIN_PASSWORD', '@Tabish321')
        if (request.form.get('username') == admin_email and
                request.form.get('password') == admin_pass):
            session['admin'] = True
            return redirect(url_for('admin_dashboard'))
        flash('Invalid credentials.', 'error')
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    return redirect(url_for('index'))

@app.route('/admin')
@admin_required
def admin_dashboard():
    db  = get_db()
    cur = db.cursor()
    cur.execute("SELECT p.*, u.name AS poster_name, u.email AS poster_email FROM posts p LEFT JOIN users u ON p.user_id=u.id ORDER BY p.created_at DESC")
    posts = cur.fetchall()
    cur.execute("SELECT COUNT(*) AS c FROM posts WHERE status='active'")
    active = cur.fetchone()['c']
    cur.execute("SELECT COUNT(*) AS c FROM posts WHERE status='resolved'")
    resolved = cur.fetchone()['c']
    cur.execute("SELECT COUNT(*) AS c FROM posts WHERE type='lost'")
    lost = cur.fetchone()['c']
    cur.execute("SELECT COUNT(*) AS c FROM posts WHERE type='found'")
    found = cur.fetchone()['c']
    cur.execute("SELECT COUNT(*) AS c FROM users WHERE is_verified=1")
    users_v = cur.fetchone()['c']
    cur.execute("SELECT COUNT(*) AS c FROM users")
    users_t = cur.fetchone()['c']
    db.close()
    stats = {
        'active': active, 'resolved': resolved,
        'lost': lost, 'found': found,
        'users': users_v, 'all_users': users_t
    }
    return render_template('admin.html', posts=posts, stats=stats)

@app.route('/admin/users')
@admin_required
def admin_users():
    db  = get_db()
    cur = db.cursor()
    cur.execute("SELECT * FROM users ORDER BY created_at DESC")
    users = cur.fetchall()
    db.close()
    return render_template('admin_users.html', users=users)

@app.route('/admin/delete/<int:post_id>')
@admin_required
def admin_delete(post_id):
    db  = get_db()
    cur = db.cursor()
    cur.execute("SELECT photo FROM posts WHERE id=%s", (post_id,))
    row = cur.fetchone()
    if row and row['photo']:
        path = os.path.join(app.config['UPLOAD_FOLDER'], row['photo'])
        if os.path.exists(path):
            os.remove(path)
    cur.execute("DELETE FROM posts WHERE id=%s", (post_id,))
    db.commit()
    db.close()
    flash('Post deleted.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete-user/<int:user_id>')
@admin_required
def admin_delete_user(user_id):
    db  = get_db()
    cur = db.cursor()
    cur.execute("DELETE FROM users WHERE id=%s", (user_id,))
    db.commit()
    db.close()
    flash('User deleted.', 'success')
    return redirect(url_for('admin_users'))


# ══════════════════════════════════════════════════════════════
#  USER PROFILE
# ══════════════════════════════════════════════════════════════
@app.route('/profile')
@login_required
def profile():
    db  = get_db()
    cur = db.cursor()
    cur.execute("SELECT * FROM users WHERE id=%s", (session['user_id'],))
    user = cur.fetchone()
    cur.execute("SELECT * FROM posts WHERE user_id=%s ORDER BY created_at DESC", (session['user_id'],))
    my_posts = cur.fetchall()
    db.close()
    return render_template('profile.html', user=user, my_posts=my_posts)

@app.route('/profile/upload-pic', methods=['POST'])
@login_required
def upload_profile_pic():
    file = request.files.get('profile_pic')
    if not file or not file.filename:
        flash('No file selected.', 'error')
        return redirect(url_for('profile'))
    if not allowed_file(file.filename):
        flash('Only image files allowed (JPG, PNG, GIF, WEBP).', 'error')
        return redirect(url_for('profile'))
    ext = file.filename.rsplit('.', 1)[1].lower()
    pic_name = f"avatar_{session['user_id']}.{ext}"
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], pic_name))
    db  = get_db()
    cur = db.cursor()
    cur.execute("UPDATE users SET profile_pic=%s WHERE id=%s", (pic_name, session['user_id']))
    db.commit()
    db.close()
    session['user_pic'] = pic_name
    flash('Profile picture updated!', 'success')
    return redirect(url_for('profile'))


# ══════════════════════════════════════════════════════════════
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
