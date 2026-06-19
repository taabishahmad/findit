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

# ── Upload config ──────────────────────────────────────────────
UPLOAD_FOLDER      = os.path.join('static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
app.config['UPLOAD_FOLDER']      = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024   # 5 MB
os.makedirs(UPLOAD_FOLDER, exist_ok=True)  # create uploads dir if missing

# ── Email config  (Gmail SMTP — fill your credentials) ────────
MAIL_SERVER   = 'smtp.gmail.com'
MAIL_PORT     = 587
MAIL_USERNAME = 'tabish.bscs4969@student.iiu.edu.pk'
MAIL_PASSWORD = 'kbnp onbn ffsa phyy'
MAIL_FROM     = 'FindIt <tabish.bscs4969@student.iiu.edu.pk>'


OPENAI_API_KEY = 'API'

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
    """Standard email format check."""
    pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    return bool(re.match(pattern, email.strip()))

def is_iiui_email(email):
    """
    Validate IIUI student email format:
    firstname.DEGREE+REGNUM@student.iiu.edu.pk
    e.g. tabish.bscs4969@student.iiu.edu.pk
    - firstname: letters only
    - degree: letters only (bscs, bba, bsee etc.)
    - regnum: 1-5 digits
    - domain: must be @student.iiu.edu.pk
    """
    pattern = r'^[a-zA-Z]+\.[a-zA-Z]+[0-9]{1,5}@student\.iiu\.edu\.pk$'
    return bool(re.match(pattern, email.strip().lower()))

def is_valid_phone(phone):
    # Accept formats: 03XX-XXXXXXX, 03XXXXXXXXX, +923XXXXXXXXX
    cleaned = re.sub(r'[\s\-]', '', phone)
    return bool(re.match(r'^(\+92|0)3[0-9]{9}$', cleaned))

def send_otp_email(to_email, otp, purpose='verify'):
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
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False

def store_otp(email, purpose='verify'):
    otp    = generate_otp()
    expiry = datetime.now() + timedelta(minutes=10)
    db  = get_db()
    cur = db.cursor()
    # Invalidate old OTPs
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
#  AI CHATBOT HELPER
# ══════════════════════════════════════════════════════════════
def load_items_context():
    """Load items.csv as context string for the AI."""
    ctx = []
    csv_path = os.path.join('data', 'items.csv')
    if os.path.exists(csv_path):
        with open(csv_path, newline='', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                ctx.append(
                    f"- {row['item']} ({row['category']}): {row['tips']}"
                )
    return '\n'.join(ctx)

def get_active_posts_summary():
    """Summarise live DB posts for AI context."""
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

# ══════════════════════════════════════════════════════════════
#  AUTH ROUTES
# ══════════════════════════════════════════════════════════════

# ── Register ──────────────────────────────────────────────────
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

        # ── Validation ────────────────────────────────────────
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
            return render_template('register.html',
                                   name=name, email=email, phone=phone)

        # ── Check email uniqueness ────────────────────────────
        db  = get_db()
        cur = db.cursor()
        cur.execute("SELECT id FROM users WHERE email=%s", (email,))
        if cur.fetchone():
            db.close()
            flash('An account with this email already exists.', 'error')
            return render_template('register.html', name=name, email=email, phone=phone)

        # ── Hash password & insert ────────────────────────────
        pw_hash = generate_password_hash(password)
        cur.execute(
            "INSERT INTO users (name, email, phone, password_hash, is_verified) "
            "VALUES (%s,%s,%s,%s,0)",
            (name, email, phone, pw_hash)
        )
        db.commit()
        db.close()

        # ── Send OTP ──────────────────────────────────────────
        otp = store_otp(email, 'verify')
        ok  = send_otp_email(email, otp, 'verify')

        session['pending_verify_email'] = email
        if ok:
            flash('Account created! Check your email for the OTP to verify your account.', 'success')
        else:
            flash('Account created! Email delivery failed — use OTP shown on this page for demo.', 'info')
            flash(f'DEMO OTP: {otp}', 'info')   # Remove in production

        return redirect(url_for('verify_email'))

    return render_template('register.html')


# ── Verify Email OTP ─────────────────────────────────────────
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


# ── Resend OTP ────────────────────────────────────────────────
@app.route('/resend-otp')
def resend_otp():
    email = session.get('pending_verify_email')
    if not email:
        return redirect(url_for('register'))
    otp = store_otp(email, 'verify')
    ok  = send_otp_email(email, otp, 'verify')
    if ok:
        flash('New OTP sent to your email.', 'success')
    else:
        flash(f'Email failed. DEMO OTP: {otp}', 'info')
    return redirect(url_for('verify_email'))


# ── Login ─────────────────────────────────────────────────────
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
            send_otp_email(email, otp, 'verify')
            flash('Please verify your email first. A new OTP has been sent.', 'info')
            return redirect(url_for('verify_email'))

        session['user_id']    = user['id']
        session['user_name']  = user['name']
        session['user_email'] = user['email']
        session['user_pic']   = user.get('profile_pic') or ''
        flash(f"Welcome back, {user['name']}!", 'success')
        return redirect(url_for('index'))

    return render_template('login.html')


# ── Forgot Password ───────────────────────────────────────────
@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        db  = get_db()
        cur = db.cursor()
        cur.execute("SELECT id FROM users WHERE email=%s", (email,))
        user = cur.fetchone()
        db.close()
        # Always show success (don't reveal if email exists)
        if user:
            otp = store_otp(email, 'reset')
            ok  = send_otp_email(email, otp, 'reset')
            if not ok:
                flash(f'Email failed. DEMO OTP: {otp}', 'info')
        session['pending_reset_email'] = email
        flash('If this email is registered, an OTP has been sent.', 'success')
        return redirect(url_for('reset_password'))
    return render_template('forgot_password.html')


# ── Reset Password ────────────────────────────────────────────
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
            for e in errors: flash(e, 'error')
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


# ── Logout ────────────────────────────────────────────────────
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

    return render_template('index.html', posts=posts,
                           search=search, filter=filter_)


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

        # Validate phone
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
            """INSERT INTO posts
               (user_id, title, description, location, type, contact, date_lost, photo, status)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'active')""",
            (session['user_id'], title, description, location,
             item_type, contact, date_lost, photo_name)
        )
        db.commit()
        db.close()

        flash('Your post has been submitted successfully!', 'success')
        return redirect(url_for('index'))

    return render_template('post.html', form={})


# ── View single post ──────────────────────────────────────────
@app.route('/post/<int:post_id>')
def view_post(post_id):
    db  = get_db()
    cur = db.cursor()
    cur.execute(
        "SELECT p.*, u.name AS poster_name, u.email AS poster_email "
        "FROM posts p LEFT JOIN users u ON p.user_id=u.id WHERE p.id=%s",
        (post_id,)
    )
    post = cur.fetchone()
    db.close()

    if not post:
        flash('Post not found.', 'error')
        return redirect(url_for('index'))

    # Can this user resolve?
    can_resolve = (
        session.get('admin') or
        (session.get('user_id') and session['user_id'] == post['user_id'])
    )

    return render_template('view_post.html', post=post, can_resolve=can_resolve)


# ── Resolve post (owner or admin only) ───────────────────────
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

    # Only owner or admin
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
#  AI CHATBOT  (API endpoint)
# ══════════════════════════════════════════════════════════════
@app.route('/api/chat', methods=['POST'])
def chat():
    data        = request.get_json(silent=True) or {}
    user_msg    = data.get('message', '').strip()
    history     = data.get('history', [])   # [{role, content}, ...]

    if not user_msg:
        return jsonify({'error': 'Empty message'}), 400

    items_ctx = load_items_context()
    posts_ctx = get_active_posts_summary()

    system_prompt = f"""You are FindIt Assistant — an AI helper for FindIt, a Community Lost & Found Board at IIUI (International Islamic University Islamabad), Pakistan.

CURRENT ACTIVE POSTS ON THE BOARD:
{posts_ctx}

ITEM TIPS BY CATEGORY:
{items_ctx}

YOUR ROLE:
- Answer questions about specific lost/found items using the board data above
- If a user asks "who found my wallet" or "has anyone found X", check the active posts above and tell them
- Help users describe items, suggest where to look, guide them to post on FindIt
- Be warm, direct, and genuinely helpful like a friend

STRICT RULES:
- Reply in 2-4 short sentences maximum — never write long paragraphs
- If the item appears in the active posts above, mention it specifically
- Never say "I'm sorry to hear that" as your first sentence — be action-oriented
- If user writes in Urdu, reply in Urdu
- Never make up contact numbers or personal details
"""

    messages = []
    for h in history[-8:]:  # Last 8 messages for context
        if h.get('role') in ('user', 'assistant') and h.get('content'):
            messages.append({'role': h['role'], 'content': h['content']})
    messages.append({'role': 'user', 'content': user_msg})

    reply = call_anthropic(messages, system_prompt)

    if not reply:
        # Smart fallback — only used when Groq API is unavailable
        ul = user_msg.lower()
        # Check message context more carefully
        is_lost_context  = any(w in ul for w in ['i lost', 'i have lost', 'missing', "can't find", 'i misplaced'])
        is_found_context = any(w in ul for w in ['i found', 'i have found', 'picked up', 'someone found'])
        is_how_context   = any(w in ul for w in ['how to', 'how do', 'how can', 'how post', 'how submit', 'guide me'])
        is_search_context= any(w in ul for w in ['who found', 'who lost', 'has anyone', 'did anyone', 'can you tell', 'tell me who'])

        if is_search_context:
            reply = f"I can see active posts on the board right now. Check the main board and use the search bar to look for your item by name or location. If someone posted it, it will appear there. You can also post your lost item so finders can contact you directly!"
        elif is_lost_context:
            reply = "I'm sorry to hear that! Here's what to do: 1) Post your lost item on FindIt right now with a clear description and photo. 2) Check the security office — they hold found items daily. 3) Search the board to see if anyone has already posted it as found."
        elif is_found_context:
            reply = "That's great that you want to return it! Post a 'Found' item on FindIt with a photo. Include where you found it and your contact number. The owner will see it and can WhatsApp or SMS you directly from the post."
        elif is_how_context:
            reply = "To post on FindIt: 1) Register with your IIUI student email. 2) Verify your email with the OTP. 3) Click '+ Post Item' in the navbar. 4) Choose Lost or Found, fill in details and add a photo. 5) Submit — your post appears immediately on the board!"
        else:
            reply = "Hello! I'm FindIt Assistant, powered by Groq AI. I can help you with lost or found items at IIUI. Tell me what happened — did you lose something or find something? I can guide you through posting it on the board."

    # Save to DB if user is logged in
    if session.get('user_id'):
        try:
            sid = data.get('session_id', 'anon')
            db  = get_db()
            cur = db.cursor()
            cur.execute(
                "INSERT INTO chat_history (user_id, session_id, role, message) VALUES (%s,%s,'user',%s)",
                (session['user_id'], sid, user_msg)
            )
            cur.execute(
                "INSERT INTO chat_history (user_id, session_id, role, message) VALUES (%s,%s,'assistant',%s)",
                (session['user_id'], sid, reply)
            )
            db.commit()
            db.close()
        except:
            pass

    return jsonify({'reply': reply})


# ══════════════════════════════════════════════════════════════
#  AI ITEM SUGGESTION  (helper for post form)
# ══════════════════════════════════════════════════════════════
@app.route('/api/suggest', methods=['POST'])
@login_required
def ai_suggest():
    data    = request.get_json(silent=True) or {}
    title   = data.get('title', '').strip()
    desc    = data.get('description', '').strip()
    itype   = data.get('type', 'lost')

    if not title:
        return jsonify({'suggestion': ''})

    system = "You are a helpful assistant for a Lost & Found board. Given an item name and description, suggest a better, more detailed description that will help someone identify the item. Keep it under 60 words. Be specific about colour, brand, size, and identifying features."
    messages = [{'role': 'user', 'content': f"Item: {title}\nType: {itype}\nDescription: {desc}\n\nSuggest an improved description:"}]
    reply = call_anthropic(messages, system)
    return jsonify({'suggestion': reply or ''})


# ══════════════════════════════════════════════════════════════
#  ADMIN ROUTES
# ══════════════════════════════════════════════════════════════
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if (request.form.get('username') == 'tabishahmadaiengineer@gmail.com' and
                request.form.get('password') == '@Tabish321'):
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

    cur.execute("SELECT p.*, u.name AS poster_name, u.email AS poster_email "
                "FROM posts p LEFT JOIN users u ON p.user_id=u.id "
                "ORDER BY p.created_at DESC")
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
        'active':    active,
        'resolved':  resolved,
        'lost':      lost,
        'found':     found,
        'users':     users_v,      # verified users — matches {{ stats.users }} in template
        'all_users': users_t       # total registered — matches {{ stats.all_users }}
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
    cur.execute("SELECT * FROM posts WHERE user_id=%s ORDER BY created_at DESC",
                (session['user_id'],))
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
    # Save with user-specific name to avoid collisions
    ext = file.filename.rsplit('.', 1)[1].lower()
    pic_name = f"avatar_{session['user_id']}.{ext}"
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], pic_name))
    db  = get_db()
    cur = db.cursor()
    cur.execute("UPDATE users SET profile_pic=%s WHERE id=%s",
                (pic_name, session['user_id']))
    db.commit()
    db.close()
    session['user_pic'] = pic_name   # refresh navbar pic immediately
    flash('Profile picture updated!', 'success')
    return redirect(url_for('profile'))


# ══════════════════════════════════════════════════════════════
# FIND THIS:
if __name__ == '__main__':
    app.run(debug=True)

# REPLACE WITH THIS:
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
