from flask import Flask, render_template, request, jsonify, redirect, url_for, g, session 
from functools import wraps
import sqlite3
import time
import uuid
import os
import json 
from datetime import datetime
from flask import session, has_request_context
import dotenv
dotenv.load_dotenv() # Load variables from .env file

# --- FLASK-MAIL IMPORTS ---
from flask_mail import Mail, Message
import random # For OTP generation

# --- GEMINI/LLM IMPORTS ---
genai = None 
APIError = Exception
ResourceExhaustedError = Exception

try:
    from google import genai
    from google.genai.errors import APIError as GenaiAPIError
    from google.genai.errors import ResourceExhaustedError as GenaiResourceExhaustedError
    APIError = GenaiAPIError
    ResourceExhaustedError = GenaiResourceExhaustedError
except Exception as e: # Modified to catch the import error
    # --- ADDED DEBUG CHECK ---
    print(f"*** DEBUG CHECK: Google genai IMPORT FAILED with error: {e}") 
    # -------------------------

# --- GLOBAL LLM CLIENT INITIALIZATION (Using .env) ---
client = None 
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# --- ADDED DEBUG CHECK ---
print(f"*** DEBUG CHECK: GEMINI_API_KEY value is: {'******' if GEMINI_API_KEY else 'MISSING'}") 
# -------------------------

if genai and GEMINI_API_KEY:
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        print("✅ Gemini Client initialized successfully.")
    except Exception as e:
        print(f"⚠️ WARNING: Failed to initialize Gemini Client. Error: {e}")
else:
    print("⚠️ LLM Service Disabled. GEMINI_API_KEY is missing or google-genai failed to import.")


# --- APP CONFIGURATION ---
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'default_strong_secret_key_change_me')

# --- FLASK-MAIL CONFIGURATION (Using .env Variables) ---
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('GMAIL_SENDER_EMAIL')
app.config['MAIL_PASSWORD'] = os.getenv('GMAIL_APP_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('GMAIL_SENDER_EMAIL')

mail = Mail(app)

# --- EMAIL RECIPIENTS CONFIGURATION ---
HOI_MANAGEMENT_EMAILS = [
    "santhoshwebworker@gmail.com",
    "jeysuryaajagadeesan@gmail.com",
    # Add other HOI management emails here
]

# --- DATABASE CONFIGURATION ---
DATABASE = 'executive_dashboard.db'
ONE_DAY_SECONDS = 24 * 60 * 60
REVIEWER_USER = "HOI Admin" 

# -------------------------------------------------------------------------------------
# 1. DATABASE CONNECTION & LOGGING FUNCTIONS
# -------------------------------------------------------------------------------------

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def log_activity(event, description, type):
    try:
        db = get_db()
        current_time = time.time()
        if has_request_context():
            user = session.get('user', 'UNAUTHENTICATED_USER') 
        else:
            user = 'SYSTEM_INIT' 
        
        db.execute("""
            INSERT INTO activities (timestamp, user, event, description, type)
            VALUES (?, ?, ?, ?, ?)
        """, (current_time, user, event, description, type))
        db.commit()
    except Exception as e:
        print(f"Error logging activity (event: {event}): {e}")

def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        
        # 1. Submissions Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS submissions (
                id TEXT PRIMARY KEY, form TEXT NOT NULL, user TEXT NOT NULL, subject TEXT NOT NULL,
                data TEXT, status TEXT NOT NULL, submittedAt REAL NOT NULL, approvedAt REAL,
                reviewedBy TEXT, remarks TEXT
            )
        """)
        
        # 2. Users Table 
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT, -- Retained for compatibility but not used for login
                role TEXT NOT NULL, 
                form_access TEXT 
            )
        """)
        
        # 3-5. Activities, Chat History, OTP Store Tables
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp REAL NOT NULL, user TEXT NOT NULL,
                event TEXT NOT NULL, description TEXT, type TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp REAL NOT NULL, user_message TEXT NOT NULL,
                assistant_reply TEXT, session_id TEXT 
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS otp_store (
                email TEXT PRIMARY KEY, otp TEXT NOT NULL, timestamp REAL NOT NULL
            )
        """)
        db.commit() 
        
        # --- INITIAL HOI ADMIN SEEDING (Reviewers) ---
        for email in HOI_MANAGEMENT_EMAILS:
            # Add HOI Admins with 'reviewer' role if they don't exist (password_hash is NULL)
            if email:
                db.execute("INSERT OR IGNORE INTO users (username, role) VALUES (?, ?)", (email, 'reviewer'))
                print(f"Added HOI Reviewer: {email}")

        # --- SUBMITTER SEEDING (27 Users - EXAMPLE DATA) ---
        submitters_list = [
            # ('Email Address', 'Form Name to Access') - Must create these HTML files in templates/forms/
            ('e22ec008@shanmugha.edu.in', 'academics.html'), # Example Form 1
            ('mercysan232007@gmail.com', 'accounts.html'), # Example Form 2
            ('e22ai002@shanmugha.edu.in', 'accreditation.html'),
            ('submitter4@test.com', 'admission.html'),
            ('submitter5@test.com', 'affiliations.html'),
            ('submitter6@test.com', 'ahs.html'),
            ('submitter7@test.com', 'boys_hostel.html'),
            ('submitter8@test.com', 'branding_marketing.html'),
            ('submitter9@test.com', 'budget.html'),
            ('submitter10@test.com', 'engineering.html'),
            ('submitter11@test.com', 'event_management.html'),
            ('submitter12@test.com', 'girls_hostel.html'),
            ('submitter13@test.com', 'guestservice.html'),
            ('submitter14@test.com', 'Hr.html'),
            ('submitter15@test.com', 'incubation.html'),
            ('submitter16@test.com', 'infra_operation.html'),
            ('submitter17@test.com', 'It_Infra.html'),
            ('submitter18@test.com', 'mess_management.html'),
            ('submitter19@test.com', 'new_institution.html'),
            ('submitter20@test.com', 'nursing.html'),
            ('submitter21@test.com', 'pharmacy.html'),
            ('submitter22@test.com', 'purchase.html'),
            ('submitter23@test.com', 'research.html'),
            ('submitter24@test.com', 'safety.html'),
            ('submitter25@test.com', 'security.html'),
            ('submitter26@test.com', '.html'),
            ('submitter27@test.com', 'transport.html'),
        ]
        
        for email, form_name in submitters_list:
            try:
                # Inserting into the 'form_access' column
                db.execute("""
                    INSERT OR IGNORE INTO users (username, role, form_access) 
                    VALUES (?, ?, ?)
                """, (email, 'submitter', form_name))
            except sqlite3.IntegrityError:
                pass 
            
        db.commit()
        print("✅ Database initialization complete: All tables ensured and users seeded.")

# -------------------------------------------------------------------------------------
# 2. HELPER FUNCTIONS 
# -------------------------------------------------------------------------------------

def check_and_move_to_pending():
    db = get_db()
    cursor = db.cursor()
    now = time.time()
    cursor.execute("""
        UPDATE submissions SET status = 'pending' 
        WHERE status = 'activity' AND submittedAt < ?
    """, (now - ONE_DAY_SECONDS,))
    if cursor.rowcount > 0:
        db.commit()
        log_activity("System Check", f"Moved {cursor.rowcount} submissions to PENDING (Overdue).", "AUTOMATION")
    return cursor.rowcount

def send_notification_email(recipient, subject, body):
    try:
        msg = Message(subject, recipients=[recipient], body=body)
        with app.app_context(): 
            mail.send(msg)
        print(f"✅ EMAIL SENT TO: {recipient} (Subject: {subject})")
        return True
    except Exception as e:
        print(f"❌ ERROR: Failed to send email to {recipient}. SMTP Error: {e}")
        return False

def get_submission_summary():
    db = get_db()
    cursor = db.cursor()
    now_ts = time.time()
    try:
        cursor.execute("SELECT COUNT(id) FROM submissions")
        total_submissions = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(id) FROM submissions WHERE status = 'pending'")
        pending_approvals = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(id) FROM submissions WHERE status = 'alert'")
        active_alerts = cursor.fetchone()[0]
        yesterday_ts = now_ts - ONE_DAY_SECONDS
        cursor.execute("SELECT COUNT(id) FROM submissions WHERE status = 'approved' AND approvedAt > ?", (yesterday_ts,))
        approved_today = cursor.fetchone()[0]
        return {
            'total_submissions': total_submissions,
            'pending_approvals': pending_approvals,
            'active_alerts': active_alerts,
            'approved_today': approved_today
        }
    except Exception as e:
        print(f"Error calculating summary: {e}")
        return None

def get_recent_activity(count=5):
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("SELECT timestamp, event, description FROM activities ORDER BY timestamp DESC LIMIT ?", (count,))
        activities = []
        for row in cursor.fetchall():
            timestamp_dt = datetime.fromtimestamp(row['timestamp'])
            activities.append({
                'timestamp': timestamp_dt.isoformat(), 
                'action': row['event'],
                'details': row['description']
            })
        return activities
    except Exception as e:
        print(f"Error fetching activities: {e}")
        return None

# -------------------------------------------------------------------------------------
# 3. FLASK ROUTES (Unified OTP Login)
# -------------------------------------------------------------------------------------

@app.before_request
def check_pending_forms_on_request():
    if request.path.startswith('/api/') or request.path == '/dashboard' or request.path == '/':
        check_and_move_to_pending()
        
def generate_otp():
    """Generates a random 6-digit numeric OTP."""
    return str(random.randint(100000, 999999))

@app.route('/api/send_otp', methods=['POST'])
def send_otp():
    import time
    data = request.get_json()
    email = data.get('email', '').strip()

    if not email:
        return jsonify({'success': False, 'message': 'Email is required.'}), 400

    db = get_db()
    cursor = db.cursor()
    # Check if the email is a registered user (either reviewer or submitter)
    cursor.execute("SELECT role FROM users WHERE username = ?", (email,))
    user_record = cursor.fetchone()
    cursor.close()

    if not user_record:
        log_activity(f"OTP Attempt Failed: {email}", "Email not registered in the system.", "AUTH_FAIL")
        return jsonify({'success': False, 'message': 'Access denied. Email not recognized.'}), 403

    otp_code = generate_otp()
    current_time = time.time()
    
    try:
        db.execute("""
            INSERT OR REPLACE INTO otp_store (email, otp, timestamp) 
            VALUES (?, ?, ?)
        """, (email, otp_code, current_time))
        db.commit()
    except Exception as e:
        log_activity(f"OTP DB Error for {email}", f"Failed to store OTP: {e}", "ERROR")
        return jsonify({'success': False, 'message': 'Server database error.'}), 500

    role_name = "HOI Dashboard Admin" if user_record['role'] == 'reviewer' else "Form Submitter"
    
    email_subject = f"Your {role_name} Login OTP"
    email_body = (
        f"Dear User,\n\n"
        f"Your One-Time Password (OTP) for {role_name} login is: {otp_code}\n"
        f"This code is valid for 120 seconds.\n\n"
        f"Do not share this OTP with anyone."
    )
    
    if not send_notification_email(recipient=email, subject=email_subject, body=email_body):
        return jsonify({'success': False, 'message': 'Failed to send OTP email. Check server logs.'}), 500

    log_activity(f"OTP Sent to {email}", f"OTP stored successfully for {role_name}.", "AUTH")
    return jsonify({'success': True, 'message': 'OTP sent successfully.'})

@app.route('/', methods=['GET', 'POST'])
def index():
    import time 
    error = request.args.get('error')
    
    if 'user' in session:
        # Already logged in: Redirect based on existing session role
        if session.get('role') == 'reviewer':
            return redirect(url_for('dashboard'))
        elif session.get('role') == 'submitter':
            return redirect(url_for('submitter_dashboard'))

    if request.method == 'POST':
        # Unified Login form submission
        submitted_otp = request.form.get('otp', '').strip()
        submitted_email = request.form.get('email', '').strip() # Assuming the input is named 'email'
        
        if not submitted_otp or not submitted_email:
            return render_template('login.html', error="Invalid login attempt or missing data.")

        db = get_db()
        cursor = db.cursor()
        
        # 1. Check OTP validity
        cursor.execute("SELECT otp, timestamp FROM otp_store WHERE email = ?", (submitted_email,))
        otp_record = cursor.fetchone()
        
        if otp_record:
            stored_otp = otp_record['otp']
            stored_timestamp = otp_record['timestamp']
            
            if time.time() - stored_timestamp > 120:
                log_activity(f"OTP Failed for {submitted_email}", "Expired OTP.", "AUTH_FAIL")
                return render_template('login.html', error='OTP expired. Please request a new one.')
            
            elif submitted_otp == stored_otp:
                
                # 2. OTP SUCCESS: Fetch user role and form access
                cursor.execute("SELECT role, form_access FROM users WHERE username = ?", (submitted_email,))
                user_record = cursor.fetchone()
                
                if not user_record:
                    log_activity(f"OTP Success but user missing: {submitted_email}", "OTP verified but user not found in 'users' table.", "AUTH_ERROR")
                    return render_template('login.html', error='Authentication failed. User role not defined.')

                # 3. Setup Session
                session['user'] = submitted_email 
                session['role'] = user_record['role'] 
                session['form_access'] = user_record['form_access'] # Store the single assigned form
                
                db.execute("DELETE FROM otp_store WHERE email = ?", (submitted_email,))
                db.commit()
                log_activity(f"Login Success: {submitted_email}", f"Logged in as {session['role']} using OTP.", "AUTH")
                
                # 4. Redirect based on role
                if session['role'] == 'reviewer':
                    return redirect(url_for('dashboard')) # HOI Admin Dashboard
                elif session['role'] == 'submitter':
                    return redirect(url_for('submitter_dashboard')) # Submitter Dashboard
                else:
                    return render_template('login.html', error='Unknown user role.')

            else:
                log_activity(f"OTP Failed for {submitted_email}", "Incorrect OTP submitted.", "AUTH_FAIL")
                return render_template('login.html', error='Incorrect OTP.')
            
        else:
            return render_template('login.html', error='Invalid email or OTP request missing. Please send OTP first.')

    # Default GET request
    return render_template('login.html', error=error)

# -------------------------------------------------------------------------------------------------

@app.route('/dashboard')
def dashboard():
    # Only reviewers can access the main dashboard
    if 'user' not in session or session.get('role') != 'reviewer':
        return redirect(url_for('index', error="HOI Admin Authentication Required"))
    
    return render_template('dashboard.html')

@app.route('/submitter_dashboard')
def submitter_dashboard():
    # Only submitters can access this dashboard
    if 'user' not in session or session.get('role') != 'submitter':
        return redirect(url_for('index', error="Form Submitter Authentication Required"))

    # The key is to pass the SINGLE assigned form for the current user 
    assigned_form_filename = session.get('form_access') 
    
    if not assigned_form_filename:
        # Fallback if somehow the session variable is empty 
        return render_template('submitter_dashboard.html', 
                                user_email=session['user'],
                                assigned_form='')
    
    # Render the template and pass the single form filename 
    return render_template('submitter_dashboard.html', 
                            user_email=session['user'],
                            # ✅ CRITICAL: Pass the single form filename for the HTML to use
                            assigned_form=assigned_form_filename) 
    


@app.route('/logout')
def logout():
    log_activity("User Logout", f"User {session.get('user', 'Unknown')} ({session.get('role', 'Unknown')}) logged out.", "LOGOUT")
    session.clear()
    return redirect(url_for('index', error="You have been logged out."))

# --- API ROUTES (Data and Form Submissions) ---
@app.route('/api/summary', methods=['GET'])
def api_summary():
    if session.get('role') != 'reviewer': return jsonify({'error': 'Unauthorized'}), 403
    summary = get_submission_summary()
    if summary is None:
        return jsonify({'error': 'Could not fetch summary data.'}), 500
    return jsonify(summary)

@app.route('/api/activity', methods=['GET'])
def api_activity():
    if session.get('role') != 'reviewer': return jsonify({'error': 'Unauthorized'}), 403
    activities = get_recent_activity(count=10)
    if activities is None:
        return jsonify({'error': 'Could not fetch activity data.'}), 500
    return jsonify({'activities': activities})

@app.route('/api/submissions', methods=['GET'])
def get_submissions():
    # Only HOI Admin gets all submissions
    if session.get('role') == 'reviewer':
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT id, form, user, subject, status, submittedAt, approvedAt FROM submissions ORDER BY submittedAt DESC") 
        submissions_list = [dict(row) for row in cursor.fetchall()]
        return jsonify(submissions_list)
    
    # Submitter gets only their submissions (security note from the original code)
    # We return error 403 for submitter attempting to access all, forcing client-side logic to handle filtering.
    return jsonify({'error': 'Unauthorized'}), 403 
    
@app.route('/api/submission/<submission_id>', methods=['GET'])
def get_submission_details(submission_id):
    # Both reviewers and submitters (for their own) need access to this endpoint
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM submissions WHERE id = ?", (submission_id,)) 
    submission = cursor.fetchone()
    
    if submission:
        # Check authorization (Reviewer can see all, Submitter can see only their own)
        if session.get('role') == 'submitter' and submission['user'] != session.get('user'):
             return jsonify({'success': False, 'message': 'Unauthorized access to submission details.'}), 403
             
        submission_details = dict(submission)
        return jsonify({'success': True, 'submission': submission_details})
    else:
        return jsonify({'success': False, 'message': 'Submission ID not found.'}), 404

@app.route('/api/submit_form', methods=['POST'])
def submit_form():
    data = request.get_json()
    db = get_db()
    new_id = 'S' + str(uuid.uuid4())[:8].upper()
    current_time = time.time()
    
    # *** IMPORTANT: Extracting data from the client-side POST request ***
    # The client-side code will send the form_type, form_user, and subject
    form_type = data.get('form_type', 'Unknown Form')
    form_user_email = data.get('form_user', 'no-reply@hoi.com') 
    form_subject = data.get('subject', f'Submission from {form_type}')
    form_data = json.dumps(data) 
    
    try:
        db.execute("""
            INSERT INTO submissions (id, form, user, subject, data, status, submittedAt)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (new_id, form_type, form_user_email, form_subject, form_data, 'activity', current_time))
        db.commit()
        
        log_activity(f"Form Submit: {form_type}", f"New submission by {form_user_email}.", "FORM_SUBMIT")
        
        return jsonify({'success': True, 'message': 'Form submitted to Today Activity.', 'id': new_id})
        
    except Exception as e:
        db.rollback()
        log_activity(f"Form Submit Failed: {form_type}", f"Database error: {e}", "ERROR")
        return jsonify({'success': False, 'message': f'Database error: {e}'}), 500

@app.route('/api/process_approval', methods=['POST'])
def process_approval():
    # Only reviewers can process approval
    if session.get('role') != 'reviewer': return jsonify({'error': 'Unauthorized'}), 403

    data = request.get_json()
    db = get_db()
    submission_id = data.get('submission_id')
    action = data.get('action')
    remarks = data.get('remarks', 'No remarks provided.')
    current_time = time.time()

    reviewer = session.get('user', REVIEWER_USER) 
    cursor = db.cursor()
    cursor.execute("SELECT * FROM submissions WHERE id = ?", (submission_id,))
    submission = cursor.fetchone()

    if not submission:
        return jsonify({'success': False, 'message': 'Submission not found'}), 404
    
    submitter_email = submission['user']
    
    try:
        new_status = action if action in ['approved', 'disapproved', 'alert'] else 'pending' 
        
        # 1. Update DB Status
        db.execute("""
            UPDATE submissions SET status = ?, approvedAt = ?, reviewedBy = ?, remarks = ?
            WHERE id = ?
        """, (new_status, current_time, reviewer, remarks, submission_id))
        
        # 2. USER NOTIFICATION (To the submitter - the person who filled the form)
        email_sent_to_submitter = False
        email_subject = ""
        
        if new_status == 'approved':
            email_subject = f"✅ Approved: {submission['subject']}"
            email_body = f"Dear User,\n\nYour submission for '{submission['subject']}' has been **APPROVED** by {reviewer}.\n\nHOI Remarks: {remarks}\n\nThank you."
        elif new_status == 'disapproved':
            email_subject = f"❌ Action Required: {submission['subject']}"
            email_body = f"Dear User,\n\nYour submission for '{submission['subject']}' has been **DISAPPROVED** by {reviewer}.\n\n--- HOI Remarks (Reason for Disapproval) ---\n{remarks}\n-----------------------------------\n\nPlease review the form and resubmit with necessary corrections."
        elif new_status == 'alert':
            email_subject = f"⚠️ Alert Flag: {submission['subject']}"
            email_body = f"Dear User,\n\nYour submission for '{submission['subject']}' has been **FLAGGED AS ALERT** by {reviewer} for further review.\n\nHOI Remarks: {remarks}\n\nAction will be notified soon."
        
        # Send email to the submitter (user column)
        if submitter_email and submitter_email != 'System User':
            email_sent_to_submitter = send_notification_email(
                recipient=submitter_email, 
                subject=email_subject, 
                body=email_body
            )

        # 3. MANAGEMENT NOTIFICATION (To HOI Admins)
        if new_status in ['approved', 'alert']:
            internal_subject = f"🔔 HOI ALERT: {new_status.upper()} - {submission['subject']}"
            internal_body = (
                f"A submission has been processed by {reviewer} with status: **{new_status.upper()}**.\n\n"
                f"Details:\n"
                f" - Submission ID: {submission_id}\n"
                f" - Form Type: {submission['form']}\n"
                f" - Submitted By: {submission['user']}\n"
                f" - HOI Remarks: {remarks}\n"
            )
            for management_email in HOI_MANAGEMENT_EMAILS:
                send_notification_email(recipient=management_email, subject=internal_subject, body=internal_body)
        
        db.commit()
        
        log_activity(f"Approval Process: {new_status.upper()}", f"Submission {submission_id} processed by {reviewer}.", "REVIEW")
        
        message = f'Submission {new_status} and confirmation email sent to submitter ({submitter_email}).' if email_sent_to_submitter else f'Submission {new_status}. Email notification failed.'
        return jsonify({'success': True, 'message': message, 'email_sent': email_sent_to_submitter})

    except Exception as e:
        db.rollback()
        log_activity(f"Approval Failed: {submission_id}", f"Database error: {e}", "ERROR")
        return jsonify({'success': False, 'message': f'Database error: {e}'}), 500

@app.route('/forms/<form_name>')
def serve_form(form_name):
    try:
        # --- 1. Basic Security Checks (Path Traversal) ---
        if '..' in form_name or '/' in form_name:
            return "<h1>Access Denied: Invalid path in form name.</h1>", 403

        # --- 2. 🌟 CRITICAL SECURITY CHECK (Submitter Authorization) 🌟 ---
        if session.get('role') == 'submitter':
            # submitter-க்கு ஒதுக்கப்பட்ட படிவத்தின் பெயர்
            assigned_form = session.get('form_access') 
            
            # உள்நுழைந்த submitter, அவருக்கு ஒதுக்கப்பட்ட படிவத்தைத் தவிர வேறு ஒன்றைத் திறக்க முயற்சித்தால்
            if form_name != assigned_form:
                 log_activity(f"Form Access Denied: {form_name}", 
                              f"Submitter {session.get('user')} attempted to access unauthorized form.", 
                              "SECURITY_BREACH")
                 return f"""
                     <div style="font-family: sans-serif; padding: 20px; text-align: center;">
                         <h1 style="color: #FF0000;">🔒 Access Denied!</h1>
                         <p>You are only authorized to view the <code>{assigned_form}</code> form.</p>
                     </div>
                 """, 403
        
        # HOI Admin (reviewer) எந்த படிவத்தையும் பார்க்க அனுமதிக்கப்படுவார்.
        # Submitter அவருக்கு ஒதுக்கப்பட்ட படிவத்தை மட்டுமே பார்க்க முடியும்.

        return render_template(f'forms/{form_name}')
    
    except Exception as e:
        # File Not Found, Template Error, etc.
        error_message = f"Error details: {e}"
        if "TemplateNotFound" in str(e):
            error_message = f"Please ensure you have created the file: <code>templates/forms/{form_name}</code>"
        
        return f"""
            <div style="font-family: sans-serif; padding: 20px; text-align: center;">
                <h1 style="color: #D97706;">Form Not Found or Server Error!</h1>
                <p>{error_message}</p>
            </div>
        """, 404

# --- CHATBOT ROUTE (Access restricted to reviewers only) ---
@app.route('/api/chatbot_reply', methods=['POST'])
def chatbot_reply():
    if session.get('role') != 'reviewer': 
        return jsonify({"status": "ok", "reply": "Chatbot is for Reviewer access only."}), 403
    
    data = request.get_json() or {}
    user_message = data.get('message', '').lower()

    # --- 1. DASHBOARD-SPECIFIC QUERIES (Database Lookup) ---
    dashboard_keywords = ["stats", "count", "summary", "forms", "pending", "activity", "recent", "log", "alert", "usage", "status", "today activity", "today"] 
    is_dashboard_query = any(keyword in user_message for keyword in dashboard_keywords)

    if is_dashboard_query:
        if any(k in user_message for k in ["stats", "count", "summary", "forms", "pending", "alert", "status", "today activity", "today"]):
            summary = get_submission_summary()
            if summary:
                reply = (
                    f"**📊 Dashboard Summary (Live Data):**\n\n"
                    f"- **Total Submissions:** {summary['total_submissions']}\n"
                    f"- **Pending Approvals:** {summary['pending_approvals']} (Overdue)\n"
                    f"- **Active Alerts:** {summary['active_alerts']}\n"
                    f"- **Approved Today:** {summary['approved_today']}\n\n"
                    f"Ask for **'recent logs'** for system activity."
                )
            else:
                reply = "Sorry, I couldn't retrieve the submission statistics from the database right now."
            return jsonify({"status": "ok", "reply": reply})

        if any(k in user_message for k in ["recent", "log", "activity"]):
            activities = get_recent_activity(count=5)
            if activities:
                reply_lines = ["**🕒 Recent System Activity (Last 5 Events):**"]
                for i, act in enumerate(activities):
                    time_str = datetime.fromisoformat(act['timestamp']).strftime('%H:%M:%S')
                    reply_lines.append(f"{i+1}. **[{time_str}] {act['action']}**: {act['details']}")
                reply = "\n".join(reply_lines)
            else:
                reply = "No recent activity logs found."
            return jsonify({"status": "ok", "reply": reply})

    # --- 2. GENERAL LLM HANDLING (If no specific data query) ---
    if not client:
        return jsonify({"status": "ok", "reply": "LLM Chatbot is disabled (API key missing or client initialization failed)."}), 200

    try:
        prompt = (
            "You are an Executive HOI Dashboard Assistant. Your role is to provide ONLY business-related, factual, and concise answers "
            "based on the provided context (if any) or general business knowledge. DO NOT provide complex programming advice. "
            f"User Query: {user_message}"
        )
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        llm_reply = response.text
        return jsonify({"status": "ok", "reply": llm_reply})

    except ResourceExhaustedError:
        return jsonify({"status": "ok", "reply": "Sorry, the AI service has temporarily run out of quota. Please try again later."}), 200
    except APIError:
        return jsonify({"status": "ok", "reply": "There was an API error communicating with the AI service. Check the API key and service status."}), 200
    except Exception as e:
        return jsonify({"status": "error", "reply": f"An unexpected error occurred in the chatbot service: {e}"}), 500


# -------------------------------------------------------------------------------------
# 4. STARTUP BLOCK
# -------------------------------------------------------------------------------------

if __name__ == '__main__':
    print("Loading environment variables from .env...")
    print(f"Starting Flask server. Database: {DATABASE}")
    
    # *** FIX: init_db() called correctly before app.run() ***
    init_db()

    os.makedirs('templates/forms', exist_ok=True) 
    app.run(debug=True)