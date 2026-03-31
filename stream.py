import cv2
import numpy as np
import requests
from flask import Flask, Response, render_template_string, jsonify
from flask_cors import CORS
import mediapipe as mp
import time

app = Flask(__name__)
CORS(app) # Opens t' gates

# --- T' TARGET ---
PI_IP = "raspberry.local"
STREAM_URL = f"http://{PI_IP}:5000/video"

# --- AI SETUP ---
DETECTION_BACKEND = "opencv"
face_detector = None
haar_face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

if hasattr(mp, "solutions") and hasattr(mp.solutions, "face_detection"):
    DETECTION_BACKEND = "mediapipe"
    mp_face_detection = mp.solutions.face_detection
    
    # --- T' CROWD FIX ---
    # Ripped out model_selection=1. It's back to t' standard brain that works on screens.
    face_detector = mp_face_detection.FaceDetection(min_detection_confidence=0.2)

# Globals for t' memory and t' 5-second lock
current_count = 0
confirmed_status = "STARTUP"
raw_status_memory = "STARTUP"
status_change_timer = time.time()

def detect_faces(frame):
    if DETECTION_BACKEND == "mediapipe" and face_detector is not None:
        # Flip to true RGB for t' AI brain
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
    print(f"Marchin' on t' Pi stream at: {STREAM_URL}")
    
    try:
        # We rip t' raw bytes directly. No OpenCV network bugs survive this.
        stream = requests.get(STREAM_URL, stream=True, timeout=10)
    except Exception as e:
        print(f"ERROR: Cannot reach Pi at {PI_IP}. Check connections.")
        return

    bytes_data = b''
    for chunk in stream.iter_content(chunk_size=1024):
        bytes_data += chunk
        a = bytes_data.find(b'\xff\xd8')
        b = bytes_data.find(b'\xff\xd9')
        
        if a != -1 and b != -1:
            jpg = bytes_data[a:b+2]
            bytes_data = bytes_data[b+2:]
            
            # Forge t' image from raw bytes
            frame = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
            if frame is None:
                continue
            
            # --- AI MATH ---
            boxes = detect_faces(frame)
            count = len(boxes)
            for x, y, w, h in boxes:
                # Draw t' tracker boxes
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            
            # --- T' 5-SECOND IRON GATE ---
            # 1. Calculate what t' camera thinks it sees right this second
            current_raw = "SAFE"
            if count < 1:
                current_raw = "SAFE"
            elif 5 <= count < 20:
                current_raw = "WARNING"
            else:
                current_raw = "DANGER"

            # 2. If t' raw vision flickers, reset t' clock!
            if current_raw != raw_status_memory:
                raw_status_memory = current_raw
                status_change_timer = time.time()

            # 3. ONLY trigger t' Pi if t' vision has been stable for 5 solid seconds
            if time.time() - status_change_timer >= 5.0:
                if confirmed_status != raw_status_memory:
                    confirmed_status = raw_status_memory
                    try:
                        # Sendin' t' command to t' Pi
                        requests.post(
                            f"{STREAM_URL.replace('/video', '/control')}",
                            json={"status": confirmed_status.lower()},
                            timeout=2,
                        )
                        print(f"COMMAND LOCKED AND SENT TO PI: {confirmed_status}")
                    except Exception:
                        print("Failed to trigger Pi hardware.")

            current_count = count
                    
            # Stamp t' final locked status on t' glass
            cv2.putText(frame, f"Faces: {count} | {confirmed_status} (LOCKED)", (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 3)

            # Package it back up for t' web dashboard
            ret, buffer = cv2.imencode('.jpg', frame)
            frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

# --- T' WEB DASHBOARD (YER PROOF) ---
@app.route('/')
def dashboard():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Crowd Rakshak</title>
        <style>
            body { background-color: #121212; color: white; font-family: sans-serif; text-align: center; padding: 40px; }
            img { border: 4px solid #0a84ff; border-radius: 12px; max-width: 100%; box-shadow: 0 0 20px rgba(10, 132, 255, 0.3); }
            h1 { color: #0a84ff; text-transform: uppercase; letter-spacing: 2px;}
            p { color: #888; font-size: 18px; }
        </style>
    </head>
    <body>
        <h1>CROWD RAKSHAK</h1>
        <p>EMERGENCY RESPONSE SYSTEM</p>
        <img src="/ai_video" alt="Waitin' for AI stream..." />
    </body>
    </html>
    """
    return render_template_string(html)

@app.route('/ai_video')
def ai_video():
    return Response(generate_ai_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

# --- T' API FOR T' FLUTTER APP ---
@app.route('/api/status')
def api_status():
    return jsonify({"count": current_count, "status": confirmed_status})

if __name__ == '__main__':
    print("LAPTOP BRAIN IS FORGED. Open http://127.0.0.1:5001 in yer browser.")
    app.run(host='0.0.0.0', port=5001)
