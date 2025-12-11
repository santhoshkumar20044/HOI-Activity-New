# app.py
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, abort
import os, json
from datetime import datetime
import sqlite3
from flask_bcrypt import Bcrypt
import smtplib
from email.mime.text import MIMEText
from functools import wraps
from dotenv import load_dotenv
load_dotenv()

# --- 🚀 LLM API Imports (optional) ---
try:
    from google import genai
    from google.genai.errors import APIError
except Exception:
    genai = None
    APIError = Exception

# -----------------------
# Configuration
# -----------------------
DATABASE = 'hoidb.sqlite'

EMAIL_CONFIG = {
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "sender_email": os.environ.get("SMTP_SENDER_EMAIL", "your_hoi_dashboard_email@gmail.com"),
    "sender_password": os.environ.get("SMTP_APP_PASSWORD", "your_app_password_here")
}

HOI_MEMBERS = [
    "ed_sir@example.com",
    "js_mam@example.com",
    "ao_sir@example.com",
    "alerts_user@example.com"
]

# -----------------------
# Flask and LLM Initialization
# -----------------------
app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "hoicenter_secret_key_0123_temp")
bcrypt = Bcrypt(app)

client = None
if genai is not None:
    try:
        client = genai.Client()
        print("✅ Gemini Client Initialized successfully.")
    except Exception as e:
        print(f"⚠️ WARNING: Gemini Client Initialization failed. General chat will not work. Error: {e}")
        client = None
else:
    client = None

# -----------------------
# Database & Utilities
# -----------------------

def get_db(db_name_override=None):
    db_path = db_name_override if db_name_override else DATABASE
    try:
        # If your app uses threads, you might need check_same_thread=False
        conn = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as err:
        print(f"Database Connection Error: {err}")
        return None

def serialize_row(row):
    return dict(row)

def log_activity(title, description, action_type):
    conn = get_db()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO activity_log (timestamp, user, action, details, type)
                VALUES (?, ?, ?, ?, ?)
            """, (datetime.now().isoformat(), session.get('user', 'System'), title, description, action_type))
            conn.commit()
        except sqlite3.Error as err:
            print(f"Logging Error: {err}")
        finally:
            try:
                cur.close()
            except Exception:
                pass
            conn.close()

def send_email_notification(subject, body, recipients):
    """Sends an email notification. Returns True/False."""
    if not recipients:
        return False
    if not isinstance(recipients, list):
        recipients = [recipients]
    try:
        msg = MIMEText(body, 'plain')
        msg['Subject'] = subject
        msg['From'] = EMAIL_CONFIG['sender_email']
        msg['To'] = ", ".join(recipients)

        with smtplib.SMTP(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port']) as server:
            server.starttls()
            server.login(EMAIL_CONFIG['sender_email'], EMAIL_CONFIG['sender_password'])
            server.sendmail(EMAIL_CONFIG['sender_email'], recipients, msg.as_string())

        log_activity("Email Sent", f"Subject: {subject}. To: {', '.join(recipients)}", "EMAIL")
        print(f"Email sent successfully: {subject} to {recipients}")
        return True
    except Exception as e:
        log_activity("Email Failed", f"To: {', '.join(recipients)}. Error: {e}", "EMAIL_ERROR")
        print(f"Email sending failed: {e}")
        return False

# -----------------------
# Decorators
# -----------------------
def require_login(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            is_api_call = request.path.startswith('/api/') or request.path in ('/submit_form_data', '/chatbot_reply')
            if is_api_call:
                return jsonify({"status": "error", "message": "Login session expired or authentication required."}), 401
            return redirect(url_for('index', error="You must be logged in to access the dashboard."))
        return f(*args, **kwargs)
    return decorated_function

# -----------------------
# DB Init (call once if DB not exists)
# -----------------------
def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS forms_data (
            id INTEGER PRIMARY KEY,
            form_name TEXT NOT NULL,
            institute TEXT,
            saved_by TEXT NOT NULL,
            form_content TEXT,
            status TEXT NOT NULL,
            is_alert INTEGER,
            saved_at TEXT,
            action_by TEXT,
            action_remarks TEXT,
            action_at TEXT,
            approved_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY,
            timestamp TEXT,
            user TEXT,
            action TEXT,
            details TEXT,
            type TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL
        )
    """)

    # Dev users
    try:
        password_hash = bcrypt.generate_password_hash('password').decode('utf-8')
        cursor.execute("INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)", ('testuser', password_hash, 'HOI'))
        cursor.execute("INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)", ('staff', bcrypt.generate_password_hash('staffpass').decode('utf-8'), 'STAFF'))
    except sqlite3.IntegrityError:
        pass

    conn.commit()
    conn.close()

# Uncomment and run once if database not initialized:
# init_db()

# -----------------------
# Helper Data Fetching
# -----------------------
def get_submission_summary():
    conn = get_db()
    if not conn:
        return None
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(id) as total FROM forms_data")
        total = cur.fetchone()['total'] or 0
        cur.execute("SELECT COUNT(id) as pending FROM forms_data WHERE status = 'pending'")
        pending = cur.fetchone()['pending'] or 0
        cur.execute("SELECT COUNT(id) as alerts FROM forms_data WHERE is_alert = 1 AND status = 'pending'")
        alerts = cur.fetchone()['alerts'] or 0

        today = datetime.now().strftime('%Y-%m-%d')
        cur.execute("SELECT COUNT(id) as approved_today FROM forms_data WHERE status = 'approved' AND approved_at LIKE ?", (today + '%',))
        approved_today = cur.fetchone()['approved_today'] or 0

        return {
            'total_submissions': total,
            'pending_approvals': pending,
            'active_alerts': alerts,
            'approved_today': approved_today
        }
    except sqlite3.Error as err:
        print(f"Summary Error: {err}")
        return None
    finally:
        conn.close()

def get_recent_activity(count=5):
    conn = get_db()
    if not conn:
        return []
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT action, details, timestamp
            FROM activity_log
            ORDER BY timestamp DESC
            LIMIT ?
        """, (count,))
        rows = cur.fetchall()
        return [dict(row) for row in rows]
    except sqlite3.Error as err:
        print(f"Activity Log Error: {err}")
        return []
    finally:
        conn.close()

# -----------------------
# Routes
# -----------------------
@app.route('/', methods=['GET', 'POST'])
def index():
    error = request.args.get('error')
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        conn = get_db()
        if not conn:
            return render_template('login.html', error="Database connection failed.")

        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cur.fetchone()
        cur.close()
        conn.close()

        if user and bcrypt.check_password_hash(user['password_hash'], password):
            user = dict(user)
            session['user'] = user['username']
            session['role'] = user['role']
            log_activity(f"User Login: {username}", "Successfully logged into the dashboard.", "LOGIN")
            return redirect(url_for('dashboard'))
        else:
            return render_template('dashboard.html', error="Invalid username or password.")

    return render_template('login.html', error=error)

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/logout')
def logout():
    username = session.pop('user', 'Guest')
    session.pop('role', None)
    log_activity(f"User Logout: {username}", "Logged out of the dashboard.", "LOGOUT")
    return redirect(url_for('index'))

@app.route("/api/load_form_template/<form_name>")
def api_load_form_template(form_name):
    # ensure filename is safe and ends with .html
    if '..' in form_name or form_name.startswith('/') or not form_name.endswith('.html'):
        return "Invalid form name", 404

    template_path = os.path.join(app.template_folder or 'templates', 'forms', form_name)
    if not os.path.isfile(template_path):
        print(f"Template not found: {template_path}")
        return f"Error loading form template: Failed to load form template: 404 NOT FOUND. Check templates/forms/{form_name}", 404

    try:
        template_rel = f'forms/{form_name}'
        return render_template(template_rel, username=session.get('user'))
    except Exception as e:
        print(f"Template loading error for {form_name}: {e}")
        return f"Error loading form template: Failed to load form template: 404 NOT FOUND. Check templates/forms/{form_name}", 404

# =======================================================
# API ENDPOINTS
# =======================================================

@app.route('/submit_form_data', methods=['POST'])
def submit_form_data():
    form_data = request.get_json() or {}
    form_name = form_data.get('form_name', 'Unknown Form')
    saved_by = session.get('user', 'Unknown User')
    institute = form_data.get('institute_id', 'N/A')

    is_alert = 1 if str(form_data.get('impact', '')).lower() == 'high risk' else 0
    form_content_json = json.dumps(form_data)
    current_time = datetime.now().isoformat()

    conn = get_db()
    if not conn:
        return jsonify({"status": "error", "message": "DB connection failed"}), 500

    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO forms_data
            (form_name, institute, saved_by, form_content, status, is_alert, saved_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (form_name, institute, saved_by, form_content_json, 'pending', is_alert, current_time))
        new_entry_id = cur.lastrowid
        conn.commit()
        log_activity(f"Form Submission: {form_name}", f"New submission ID {new_entry_id} saved by {saved_by}. Awaiting approval.", "SUBMISSION")
        return jsonify({
            'status': 'ok',
            'message': f'{form_name} submitted successfully and awaiting approval. It will appear in Today Activity.',
            'entry_id': new_entry_id
        }), 200
    except sqlite3.Error as err:
        conn.rollback()
        print(f"Database Error during form submission: {err}")
        return jsonify({"status": "error", "message": f"Database Error: {err}"}), 500
    finally:
        try:
            cur.close()
        except Exception:
            pass
        conn.close()

@app.route('/api/approve_submission', methods=['POST'])
def approve_submission():
    data = request.get_json() or {}
    record_id = data.get('id')
    remarks = data.get('remarks', 'Approved by HOI.')
    action_by = session.get('user', 'System/Unknown')
    action_time = datetime.now().isoformat()

    if not record_id:
        return jsonify({"status": "error", "message": "Missing ID"}), 400

    conn = get_db()
    if not conn:
        return jsonify({"status": "error", "message": "DB connection failed"}), 500

    try:
        cur = conn.cursor()
        cur.execute("SELECT form_name, saved_by FROM forms_data WHERE id = ?", (record_id,))
        record = cur.fetchone()
        if not record:
            return jsonify({"status": "error", "message": "Record not found"}), 404

        form_name, saved_by_email = record['form_name'], record['saved_by']

        cur.execute("""
            UPDATE forms_data SET status = 'approved', action_by = ?, action_remarks = ?, action_at = ?, approved_at = ?
            WHERE id = ?
        """, (action_by, remarks, action_time, action_time, record_id))
        conn.commit()

        email_subject = f"[APPROVED] HOI Form: {form_name}"
        email_body = f"The submission for {form_name} (ID: {record_id}) submitted by {saved_by_email} has been APPROVED by {action_by} at {action_time}.\n\nRemarks: {remarks}"

        # send to HOI members (non-blocking errors are handled inside send_email_notification)
        send_email_notification(email_subject, email_body, HOI_MEMBERS)

        log_activity(f"Form Approved: {form_name}", f"ID {record_id} approved by {action_by}.", "APPROVAL")
        return jsonify({"status": "ok", "message": f"{form_name} approved successfully."}), 200

    except sqlite3.Error as e:
        conn.rollback()
        return jsonify({"status": "error", "message": f"DB Error: {e}"}), 500
    finally:
        try:
            cur.close()
        except Exception:
            pass
        conn.close()

@app.route('/api/disapprove_submission', methods=['POST'])
def disapprove_submission():
    data = request.get_json() or {}
    record_id = data.get('id')
    remarks = data.get('remarks', 'Disapproved. Needs correction and resubmission.')
    action_by = session.get('user', 'System/Unknown')
    action_time = datetime.now().isoformat()

    if not record_id or not remarks:
        return jsonify({"status": "error", "message": "Missing ID or Remarks"}), 400

    conn = get_db()
    if not conn:
        return jsonify({"status": "error", "message": "DB connection failed"}), 500

    try:
        cur = conn.cursor()
        cur.execute("SELECT form_name, saved_by FROM forms_data WHERE id = ?", (record_id,))
        record = cur.fetchone()
        if not record:
            return jsonify({"status": "error", "message": "Record not found"}), 404

        form_name, saved_by_email = record['form_name'], record['saved_by']

        cur.execute("""
            UPDATE forms_data SET status = 'disapproved', action_by = ?, action_remarks = ?, action_at = ?
            WHERE id = ?
        """, (action_by, remarks, action_time, record_id))
        conn.commit()

        email_subject = f"[DISAPPROVED] HOI Form: {form_name}"
        email_body = f"Your submission for {form_name} (ID: {record_id}) has been DISAPPROVED by {action_by} at {action_time}.\n\nReason/Remarks: {remarks}\n\nAction Required: Please review the remarks and re-submit the corrected {form_name} form."

        # send only to submitter
        send_email_notification(email_subject, email_body, saved_by_email)

        log_activity(f"Form Disapproved: {form_name}", f"ID {record_id} disapproved by {action_by}.", "DISAPPROVAL")
        return jsonify({"status": "ok", "message": f"{form_name} disapproved successfully. The user has been notified to re-submit."}), 200

    except sqlite3.Error as e:
        conn.rollback()
        return jsonify({"status": "error", "message": f"DB Error: {e}"}), 500
    finally:
        try:
            cur.close()
        except Exception:
            pass
        conn.close()

# =======================================================
# Dashboard Data APIs (protected)
# =======================================================
@app.route('/api/today_activities')
def get_today_activities():
    conn = get_db()
    if not conn:
        return jsonify({"status": "error", "message": "DB connection failed"}), 500
    try:
        cur = conn.cursor()
        today_start = datetime.now().strftime('%Y-%m-%d')
        cur.execute("SELECT id, form_name, institute, saved_by, status, is_alert, saved_at FROM forms_data WHERE saved_at LIKE ? ORDER BY saved_at DESC", (today_start + '%',))
        data = cur.fetchall()
        results = [serialize_row(row) for row in data]
        return jsonify({"status": "ok", "data": results}), 200
    except sqlite3.Error as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()

@app.route('/api/pending_approvals')
def get_pending_approvals():
    conn = get_db()
    if not conn:
        return jsonify({"status": "error", "message": "DB connection failed"}), 500
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, form_name, institute, saved_by, status, is_alert, saved_at FROM forms_data WHERE status = 'pending' ORDER BY saved_at ASC")
        data = cur.fetchall()
        results = [serialize_row(row) for row in data]
        return jsonify({"status": "ok", "data": results}), 200
    except sqlite3.Error as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()

@app.route('/api/alerts')
def alerts_data():
    conn = get_db()
    if not conn:
        return jsonify({"status": "error", "message": "DB connection failed"}), 500
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, form_name, institute, saved_by, saved_at
            FROM forms_data
            WHERE is_alert = 1 AND status = 'pending'
            ORDER BY saved_at ASC
        """)
        data = [serialize_row(row) for row in cur.fetchall()]
        return jsonify({"status": "ok", "data": data}), 200
    except sqlite3.Error as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()

# =======================================================
# AJAX content loader for dashboard sections
# =======================================================
@app.route('/load_content/<section_id>')
def load_dashboard_content(section_id):
    if section_id == 'overview':
        summary = get_submission_summary()
        return render_template('overview_content.html', summary=summary)
    elif section_id == 'activity':
        return render_template('activity_table.html')
    elif section_id == 'approvals':
        return render_template('approvals_table.html')
    elif section_id == 'alerts':
        return render_template('alerts_list.html')
    elif section_id == 'forms_list':
        return render_template('forms_list.html')
    else:
        return f'<div class="p-4 text-red-500">Section {section_id} not found.</div>', 404

# =======================================================
# Chatbot
# =======================================================
@app.route('/chatbot_reply', methods=['POST'])
def chatbot_reply():
    data = request.get_json() or {}
    user_message = data.get('message', '').lower()

    dashboard_keywords = ["stats", "count", "summary", "forms", "pending", "activity", "recent", "log", "alert", "usage"]
    is_dashboard_query = any(keyword in user_message for keyword in dashboard_keywords)

    if is_dashboard_query:
        if "stats" in user_message or "count" in user_message or "summary" in user_message or "forms" in user_message or "pending" in user_message:
            summary = get_submission_summary()
            if summary:
                reply = (
                    f"**📊 Dashboard Summary (Live Data):**\n\n"
                    f"- **Total Submissions:** {summary['total_submissions']}\n"
                    f"- **Pending Approvals:** {summary['pending_approvals']}\n"
                    f"- **Active Alerts:** {summary['active_alerts']}\n"
                    f"- **Approved Today:** {summary['approved_today']}\n\n"
                    f"Ask for **'recent activity'** for logs."
                )
            else:
                reply = "Sorry, I couldn't retrieve the submission statistics from the database right now."
        elif "activity" in user_message or "usage" in user_message or "recent" in user_message or "log" in user_message:
            activities = get_recent_activity(count=5)
            if activities:
                reply = "**📰 Recent 5 Dashboard Activities (Live Data):**\n"
                for activity in activities:
                    try:
                        time_str = datetime.fromisoformat(activity['timestamp']).strftime('%I:%M %p')
                    except Exception:
                        time_str = 'Time N/A'
                    clean_desc = activity.get('details', 'No details').split('.')[0].replace('*', '')
                    reply += f"\n- [{time_str}] **{activity.get('action', 'Unknown Action')}** ({clean_desc}.)"
            else:
                reply = "No recent activity logs found in the system."
        else:
            reply = "I see you are asking about the dashboard. Try asking specifically for **'summary'** or **'recent activity'**."

        return jsonify({"status": "ok", "reply": reply})

    # General LLM handling
    if client is None:
        reply = "⚠️ **LLM Service Initialization Failed** ⚠️. Please ensure your `GEMINI_API_KEY` is set correctly."
        return jsonify({"status": "error", "reply": reply})

    try:
        original_message = data.get('message', '')
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=original_message
        )
        llm_reply = response.text
        final_reply = f"**🌐 HOI Assistant (General Knowledge):**\n\n{llm_reply}"
        return jsonify({"status": "ok", "reply": final_reply})
    except APIError:
        return jsonify({"status": "error", "reply": "External LLM service failed to respond. Check API Key or connectivity."})
    except Exception as e:
        return jsonify({"status": "error", "reply": f"An unexpected error occurred during LLM processing: {str(e)}"})

if __name__ == '__main__':
    # If running first time, uncomment the next line to create DB + seed users:
    # init_db()
    app.run(debug=True, port=5000)
3