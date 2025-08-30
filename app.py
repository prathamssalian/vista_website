from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file, jsonify
from datetime import datetime
import mysql.connector
import smtplib, json
from authlib.integrations.flask_client import OAuth
from email.message import EmailMessage
import os
from werkzeug.utils import secure_filename


app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Required for session & flash
DATA_FILE = os.path.join(app.root_path, "data", "events.json")
UPLOAD_FOLDER = os.path.join(app.root_path, "static", "images")
os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
# MySQL connection

def get_connection():
    return mysql.connector.connect(
        host='localhost',
        user='root',
        password='pssalian',
        database='vista_website'
    )

def log_login(name, email, usertype, status):
    conn = get_connection()
    cursor = conn.cursor()
    query = """
        INSERT INTO login_logs (name, email, usertype, status, login_time)
        VALUES (%s, %s, %s, %s, NOW())
    """
    cursor.execute(query, (name, email, usertype, status))
    conn.commit()
    cursor.close()
    conn.close()

# --- Google OAuth Setup ---
oauth = OAuth(app)
google = oauth.register(
    name="google",
    client_id="YOUR_GOOGLE_CLIENT_ID",
    client_secret="YOUR_GOOGLE_CLIENT_SECRET",
    access_token_url="https://accounts.google.com/o/oauth2/token",
    access_token_params=None,
    authorize_url="https://accounts.google.com/o/oauth2/auth",
    authorize_params={"access_type": "offline", "prompt": "select_account"},
    api_base_url="https://www.googleapis.com/oauth2/v1/",
    client_kwargs={"scope": "openid email profile"},
)

@app.route("/google_login")
def google_login():
    redirect_uri = url_for("authorize", _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route("/authorize")
def authorize():
    token = google.authorize_access_token()
    user_info = google.get("userinfo").json()

    email = user_info["email"]
    name = user_info.get("name", "Google User")

    session["logged_in"] = True
    session["email"] = email
    session["usertype"] = "google_user"

    log_login(name, email, "google_user", "success")
    flash("Google login successful!", "success")
    return redirect(url_for("vista"))

# --- Manual Login ---
@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["username"]
        password = request.form["password"]
        status = "failure"

        # Faculty Login
        if email.endswith("@nitte.in") and password == "faculty@123":
            session["logged_in"] = True
            session["email"] = email
            session["usertype"] = "faculty"
            flash("Faculty login successful!", "success")
            status = "success"
            log_login(name, email, "faculty", status)
            return redirect(url_for("vista"))

        # Student Login
        elif email.endswith("@nmamit.in") and password == "student@123":
            session["logged_in"] = True
            session["email"] = email
            session["usertype"] = "student"
            flash("Student login successful!", "success")
            status = "success"
            log_login(name, email, "student", status)
            return redirect(url_for("vista"))

        # Web Admin Login
        elif email == "webadmin" and password == "admin420":
            session["logged_in"] = True
            session["email"] = email
            session["usertype"] = "webadmin"
            flash("Web Admin login successful!", "success")
            status = "success"
            log_login(name, email, "webadmin", status)
            return redirect(url_for("admin_dashboard"))

        # Failure Case
        else:
            error = "Invalid credentials!"
            log_login(name, email, "unknown", status)

    return render_template("login.html", error=error)

@app.route("/branch_fund")
def branch_fund():
    if "logged_in" not in session or session["usertype"] != "student":
        flash("Please login first", "error")
        return redirect(url_for("login"))

    email = session["email"]

    # Determine payment details based on email
    if email.startswith("nnm22"):
        fund_amount = 300
        qr_image = "/static/images/chinmai.jpg"
        upi_link = f"upi://pay?pa=prathamssalian@okaxis&pn=Pratham%20S%20Salian&am={fund_amount}&cu=INR"
    else:  # nnm23 or others
        fund_amount = 400
        qr_image = "{{ url_for('static', filename='images/qr_nnm22.jpg') }}"
        upi_link = f"upi://pay?pa=prathamssalian@okaxis&pn=Pratham%20S%20Salian&am={fund_amount}&cu=INR"

    return render_template("branch_fund.html", fund_amount=fund_amount, qr_image=qr_image, upi_link=upi_link)

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully!", "success")
    return redirect(url_for("vista"))


# --- Admin Dashboard ---
@app.route("/admin_dashboard")
def admin_dashboard():
    if not session.get("logged_in") or session.get("usertype") != "webadmin":
        flash("Access denied! Only Web Admin can access this page.", "danger")
        return redirect(url_for("login"))

    return render_template("admin_dashboard.html")

@app.route('/admin_gallery')
def admin_gallery():
    return render_template('admin_gallery.html')

# ---- Manage Results ----
@app.route("/manage_results")
def manage_results():
    if session.get("usertype") != "webadmin":
        return redirect(url_for("login"))
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM results")
    results = cursor.fetchall()
    conn.close()
    return render_template("manage_results.html", results=results)

@app.route("/add_result", methods=["POST"])
def add_result():
    if session.get("usertype") != "webadmin":
        return redirect(url_for("login"))
    event = request.form["event"]
    winner = request.form["winner"]
    usn = request.form.get("usn")
    year = request.form.get("year")
    photo = request.form.get("photo")
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO results (event, winner, usn, year, photo) VALUES (%s, %s, %s, %s, %s)",
                   (event, winner, usn, year, photo))
    conn.commit()
    conn.close()
    return redirect(url_for("manage_results"))

@app.route("/delete_result/<int:id>", methods=["POST"])
def delete_result(id):
    if session.get("usertype") != "webadmin":
        return redirect(url_for("login"))
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM results WHERE id=%s", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for("manage_results"))


@app.route('/')
def home():
    return render_template('index.html')

# Load events from JSON
def load_events():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return []

# Save events to JSON
def save_events(events):
    with open(DATA_FILE, "w") as f:
        json.dump(events, f, indent=4)

@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        title = request.form.get("title")
        description = request.form.get("description")
        date = request.form.get("date")
        image_file = request.files.get("image")

        if not title or not description or not date:
            flash("All fields are required!", "danger")
            return redirect(url_for("admin"))

        filename = None
        if image_file and allowed_file(image_file.filename):
            filename = secure_filename(image_file.filename)
            image_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            image_file.save(image_path)

        events = load_events()
        events.append({
            "title": title,
            "description": description,
            "date": date,
            "image": filename if filename else ""
        })
        save_events(events)

        flash("Event added successfully!", "success")
        return redirect(url_for("admin"))

    events = load_events()
    return render_template("admin.html", events=events)

@app.route("/delete/<int:event_id>", methods=["POST"])
def delete_event(event_id):
    events = load_events()
    if 0 <= event_id < len(events):
        event = events.pop(event_id)
        if event.get("image"):
            image_path = os.path.join(app.config["UPLOAD_FOLDER"], event["image"])
            if os.path.exists(image_path):
                os.remove(image_path)
        save_events(events)
        flash("Event deleted successfully!", "success")
    else:
        flash("Invalid event ID!", "danger")
    return redirect(url_for("admin"))


@app.route("/gallery")
def gallery():
    events = load_events()
    return render_template("gallery.html", events=events)

@app.route("/event/<event_id>")
def event_detail(event_id):
    events = load_events()
    event = next((e for e in events if e["id"] == event_id), None)
    if not event:
        abort(404)
    return render_template("event_detail.html", event=event)

@app.route('/event/<event_id>')
def event(event_id):
    event = event_data.get(event_id)
    if not event:
        return "Event not found", 404
    return render_template("event_gallery.html", event=event)

@app.route('/circular')
def circular():
    return render_template('circular.html')

@app.route('/resources/2nd-year')
def second_year_resources():
    return render_template('2year.html')

@app.route('/resources/3rd-year')
def third_year_resources():
    return render_template('3year.html')

@app.route('/resources/4th-year')
def fourth_year_resources():
    return render_template('4year.html')

@app.route('/vista')
def vista():
    return render_template('vista.html')

@app.route('/team')
def team():
    return render_template('team.html')

@app.route('/past-events')
def past_events():
    return render_template('past.html')

@app.route('/admin/events')
def admin_events():
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM events ORDER BY date DESC")
    events = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("admin_events.html", events=events)

@app.route('/admin/events/add', methods=['GET', 'POST'])
def add_event():
    if request.method == 'POST':
        title = request.form['title']
        date = request.form['date']
        desc = request.form['description']
        banner = request.form['banner']  # could be file upload too

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO events (title, date, description, banner) VALUES (%s, %s, %s, %s)",
                    (title, date, desc, banner))
        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('admin_events'))
    return render_template("add_event.html")

@app.route('/admin/events/<int:event_id>/gallery', methods=['GET', 'POST'])
def manage_gallery(event_id):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    if request.method == 'POST':
        image = request.form['image']
        cur.execute("INSERT INTO event_gallery (event_id, image_path) VALUES (%s, %s)", (event_id, image))
        conn.commit()

    cur.execute("SELECT * FROM event_gallery WHERE event_id=%s", (event_id,))
    gallery = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("manage_gallery.html", gallery=gallery, event_id=event_id)


@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if 'logged_in' not in session:
        flash('Please login to send a message.', 'error')
        return redirect(url_for('login'))

    if request.method == 'POST':
        name = request.form['name']
        usn = request.form['usn']
        message = request.form['message']
        sender_email = session.get('email')

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO contacts (name, usn, email, message, submitted_at)
            VALUES (%s, %s, %s, %s, NOW())
        """, (name, usn, sender_email, message))
        conn.commit()
        cursor.close()
        conn.close()

        full_message = f"Name: {name}\nUSN: {usn}\nSender Email: {sender_email}\n\nMessage:\n{message}"
        
        try:
            send_email("Contact Form Submission", full_message, sender_email)
            flash('Message sent successfully!', 'success')
        except Exception as e:
            print(e)
            flash('Error sending message.', 'error')

        return redirect(url_for('contact'))

    return render_template('vista.html')

def send_email(subject, body, reply_to):
    sender = 'prathamssalian@gmail.com'
    password = 'ljza jhns bqno hshk'
    receiver = 'prathamssalian@gmail.com'

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = receiver
    msg['Reply-To'] = reply_to
    msg.set_content(body)

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(sender, password)
        smtp.send_message(msg)

@app.route('/results')
def show_results():
    return render_template('results.html')

@app.route('/submit_payment', methods=['POST'])
def submit_payment():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    name = request.form.get('name')
    usn = request.form.get('usn')
    txn = request.form.get('txn')

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO payments (name, usn, transaction_id, submitted_at)
        VALUES (%s, %s, %s, NOW())
    """, (name, usn, txn))
    conn.commit()
    cursor.close()
    conn.close()

    flash("Thank you for paying!", "payment")
    return redirect(url_for('vista'))

@app.route('/rsvp-submit', methods=['POST'])
def rsvp_submit():
    # Ensure user is logged in
    if 'email' not in session:
        return jsonify({'status': 'error', 'message': 'Login required'}), 403

    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'Invalid JSON data'}), 400

        name = data.get('name')
        event_title = data.get('event_title')
        email = session['email']  # always take email from session

        if not name or not event_title:
            return jsonify({'status': 'error', 'message': 'Missing required fields'}), 400

        conn = get_connection()
        cursor = conn.cursor()

        # Check for duplicate registration
        cursor.execute(
            "SELECT id FROM rsvp_data WHERE email=%s AND event_title=%s",
            (email, event_title)
        )
        if cursor.fetchone():
            return jsonify({'status': 'success', 'message': 'Already registered'})

        # Insert new RSVP
        cursor.execute(
            "INSERT INTO rsvp_data (name, email, event_title, date) VALUES (%s, %s, %s, NOW())",
            (name, email, event_title)
        )
        conn.commit()

        return jsonify({'status': 'success', 'message': 'RSVP submitted successfully'})

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    return jsonify({'status': 'success'})

@app.route('/my-registered-events', methods=['GET'])
def my_registered_events():
    if 'email' not in session:
        return jsonify({'status': 'error', 'message': 'Login required'}), 403

    email = session['email']

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT event_title, date FROM rsvp_data WHERE email=%s ORDER BY date DESC",
        (email,)
    )
    events = cursor.fetchall()
    cursor.close()
    conn.close()

    return jsonify({'status': 'success', 'events': events})


@app.route('/rsvp-check')
def rsvp_check():
    if 'logged_in' in session:
        return {'status': 'ok'}
    else:
        return {'status': 'not_logged_in'}


# Dummy event data (for demo; ideally fetch from DB `events` table)
event_data = {
    "AI Hackathon 2025": {
        "name": "AI Hackathon 2025",
        "date": "25th June 2025",
        "description": "24 hours of innovation and AI challenges. Open to all students."
    },
    "TechTalk: Blockchain": {
        "name": "TechTalk: Blockchain",
        "date": "1st July 2025",
        "description": "Lecture on blockchain trends, impact, and real use cases."
    },
    "Women in Tech Panel": {
        "name": "Women in Tech Panel",
        "date": "10th July 2025",
        "description": "Celebrating women innovators with Q&A and networking sessions."
    },
    "Internship Fair": {
        "name": "Internship Fair",
        "date": "15th July 2025",
        "description": "Meet recruiters and apply for internships in startups and MNCs."
    }
}


@app.route('/upcoming-events')
def upcoming_events():
    registered_events = []
    if 'email' in session:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT event_title FROM rsvp_data WHERE email=%s", (session['email'],))
        registered_events = [row['event_title'] for row in cursor.fetchall()]
        cursor.close()
        conn.close()

    return render_template('upcoming.html',
                           events=event_data,
                           registered_events=registered_events)



if __name__ == '__main__':
    app.run(debug=True)