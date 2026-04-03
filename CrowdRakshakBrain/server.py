import cv2
import numpy as np
import requests
from flask import Flask, Response, render_template, jsonify, request, redirect, url_for, session
from flask_cors import CORS
import mediapipe as mp
import time
from collections import deque
from datetime import datetime
import socket
import concurrent.futures

app = Flask(__name__)
CORS(app)
app.secret_key = "crowd_rakshak_secret_2024"

# --- TARGET ---
# --- T' AUTO-HUNTER ---
def hunt_for_pi():
    print("Unleashin' t' hounds to hunt down t' Pi's IP address...")
    base_ip = "192.168.137." # T' standard Windows Hotspot land
    
    def check_port(ip):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.5) # Fast strike, don't wait around
        result = sock.connect_ex((ip, 5000))
        sock.close()
        if result == 0:
            return ip
        return None

    # Send 100 scouts out to sweep t' battlefield in half a second
    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
        ips = [f"{base_ip}{i}" for i in range(2, 255)]
        for result in executor.map(check_port, ips):
            if result:
                print(f"TARGET LOCKED: T' Pi is waitin' at {result}")
                return result
                
    print("T' hounds found naught. Is t' Pi powered and connected to t' hotspot?")
    return "127.0.0.1" # Fallback so t' code doesn't crash completely

# --- T' TARGET ---
PI_IP = hunt_for_pi()
STREAM_URL = f"http://{PI_IP}:5000/video"

# --- CREDENTIALS ---
USERS = {
    "police": {"password": "police123", "role": "police"},
    "volunteer": {"password": "volunteer123", "role": "volunteer"},
}

# --- AI SETUP ---
DETECTION_BACKEND = "opencv"
face_detector = None
haar_face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

if hasattr(mp, "solutions") and hasattr(mp.solutions, "face_detection"):
    DETECTION_BACKEND = "mediapipe"
    mp_face_detection = mp.solutions.face_detection
    face_detector = mp_face_detection.FaceDetection(min_detection_confidence=0.2)

# --- GLOBALS ---
current_count = 0
confirmed_status = "STARTUP"
raw_status_memory = "STARTUP"
status_change_timer = time.time()

# --- THRESHOLDS (editable via dashboard) ---
threshold_warning = 5
threshold_danger = 20

# --- ALERT LOG (last 100 events) ---
alert_log = deque(maxlen=100)

# --- GRAPH DATA (last 30 minutes = 1800 seconds, sampled every 2s = 900 points max) ---
graph_data = deque(maxlen=900)


def log_alert(status, count, action):
    alert_log.appendleft({
        "time": datetime.now().strftime("%H:%M:%S"),
        "status": status,
        "count": count,
        "action": action
    })


def detect_faces(frame):
    if DETECTION_BACKEND == "mediapipe" and face_detector is not None:
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = face_detector.process(rgb_frame)
        boxes = []
        if results and results.detections:
            ih, iw, _ = frame.shape
            for detection in results.detections:
                bbox = detection.location_data.relative_bounding_box
                x = int(bbox.xmin * iw)
                y = int(bbox.ymin * ih)
                w = int(bbox.width * iw)
                h = int(bbox.height * ih)
                boxes.append((x, y, w, h))
        return boxes
    gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return haar_face_cascade.detectMultiScale(gray_frame, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))


def generate_ai_frames():
    global current_count, confirmed_status, raw_status_memory, status_change_timer
    global threshold_warning, threshold_danger

    last_graph_sample = time.time()

    try:
        stream = requests.get(STREAM_URL, stream=True, timeout=10)
    except Exception as e:
        print(f"ERROR: Cannot reach Pi at {PI_IP}.")
        return

    bytes_data = b''
    for chunk in stream.iter_content(chunk_size=1024):
        bytes_data += chunk
        a = bytes_data.find(b'\xff\xd8')
        b = bytes_data.find(b'\xff\xd9')

        if a != -1 and b != -1:
            jpg = bytes_data[a:b+2]
            bytes_data = bytes_data[b+2:]

            frame = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
            if frame is None:
                continue

            boxes = detect_faces(frame)
            count = len(boxes)
            for x, y, w, h in boxes:
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 100, 255), 2)

            # Determine raw status using live thresholds
            if count < threshold_warning:
                current_raw = "SAFE"
            elif count < threshold_danger:
                current_raw = "WARNING"
            else:
                current_raw = "DANGER"

            if current_raw != raw_status_memory:
                raw_status_memory = current_raw
                status_change_timer = time.time()

            if time.time() - status_change_timer >= 3.0:
                if confirmed_status != raw_status_memory:
                    confirmed_status = raw_status_memory
                    action_taken = ""
                    try:
                        requests.post(
                            f"{STREAM_URL.replace('/video', '/control')}",
                            json={"status": confirmed_status.lower()},
                            timeout=2,
                        )
                        if confirmed_status == "SAFE":
                            action_taken = "Gate opened"
                        elif confirmed_status == "WARNING":
                            action_taken = "LED yellow, standby"
                        elif confirmed_status == "DANGER":
                            action_taken = "Siren ON, Gate closed"
                        print(f"COMMAND SENT: {confirmed_status}")
                    except Exception:
                        action_taken = "Pi unreachable"
                        print("Failed to trigger Pi hardware.")
                    log_alert(confirmed_status, count, action_taken)

            current_count = count

            # Sample graph data every 2 seconds
            if time.time() - last_graph_sample >= 2.0:
                graph_data.append({
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "count": count
                })
                last_graph_sample = time.time()

            ret, buffer = cv2.imencode('.jpg', frame)
            frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')


# --- AUTH ROUTES ---
@app.route('/')
def index():
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        user = USERS.get(username)
        if user and user['password'] == password:
            session['username'] = username
            session['role'] = user['role']
            return redirect(url_for('dashboard'))
        error = "Invalid credentials. Please try again."
    return render_template('login.html', error=error)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))
    role = session.get('role', 'volunteer')
    if role == 'police':
        return render_template('dashboard_police.html', username=session['username'])
    else:
        return render_template('dashboard_volunteer.html', username=session['username'])


# --- VIDEO FEED ---
@app.route('/ai_video')
def ai_video():
    return Response(generate_ai_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


# --- API ENDPOINTS ---
@app.route('/api/status')
def api_status():
    return jsonify({
        "count": current_count,
        "status": confirmed_status,
        "threshold_warning": threshold_warning,
        "threshold_danger": threshold_danger
    })


@app.route('/api/graph')
def api_graph():
    return jsonify(list(graph_data))


@app.route('/api/alerts')
def api_alerts():
    return jsonify(list(alert_log))


@app.route('/api/thresholds', methods=['POST'])
def set_thresholds():
    if session.get('role') != 'police':
        return jsonify({"error": "Unauthorized"}), 403
    global threshold_warning, threshold_danger
    data = request.json
    threshold_warning = int(data.get('warning', threshold_warning))
    threshold_danger = int(data.get('danger', threshold_danger))
    return jsonify({"success": True, "warning": threshold_warning, "danger": threshold_danger})


@app.route('/api/manual_control', methods=['POST'])
def manual_control():
    if session.get('role') != 'police':
        return jsonify({"error": "Unauthorized"}), 403
    data = request.json
    action = data.get('action')
    try:
        requests.post(
            f"{STREAM_URL.replace('/video', '/control')}",
            json={"status": action},
            timeout=2,
        )
        log_alert("MANUAL", current_count, f"Manual override: {action}")
        return jsonify({"success": True})
    except Exception:
        return jsonify({"error": "Pi unreachable"}), 500


if __name__ == '__main__':
    print("CROWD RAKSHAK SERVER RUNNING. Open http://127.0.0.1:5001")
    app.run(host='0.0.0.0', port=5001, debug=False)
