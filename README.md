# 🛡️ Crowd Rakshak
**Real-time AI crowd monitoring & emergency response system**

Built on Raspberry Pi Zero W + MediaPipe face detection. Streams live camera footage over local Wi-Fi, detects crowd density, and automatically triggers hardware responses (LEDs, buzzer, servo gate) — all through a professional web dashboard.

---

## 🗂️ File Structure
```
crowd-rakshak/
├── stream.py                  ← runs on Raspberry Pi
├── server.py                  ← runs on laptop
└── templates/
    ├── login.html
    ├── dashboard_police.html
    └── dashboard_volunteer.html
```

---

## ⚙️ How It Works
```
Pi Camera → stream.py (port 5000) → server.py detects faces → sends status back to Pi
                                           ↓
                                   Web dashboard (port 5001)
                                           ↓
                              Police / Volunteer login views
```

| Status | Trigger | Hardware Response |
|--------|---------|-------------------|
| SAFE | Faces < warning threshold | Green LED ON, servo gate open |
| WARNING | Faces between thresholds | Yellow LED ON |
| DANGER | Faces ≥ danger threshold | Red LED ON + siren + gate closed |

Status only locks in after **5 stable seconds** — prevents false triggers.

---

## 🍓 Raspberry Pi Setup

**Requirements:** Raspberry Pi Zero W, Pi Camera Module, Raspbian OS 32-bit Lite

### 1. Flash OS
Use [Raspberry Pi Imager](https://www.raspberrypi.com/software/). In **Advanced Options** before flashing:
- Hostname: `raspberry.local`
- Enable SSH: ✅
- Wi-Fi SSID: `YUKI` / Password: `00000000` / Country: `IN`

### 2. SSH into Pi
```bash
ssh pi@raspberry.local
# default password: raspberry
```

### 3. Enable Camera
```bash
sudo raspi-config
# Interface Options → Legacy Camera → Enable → Reboot
```

### 4. Install dependencies
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-picamera2 python3-opencv
pip3 install flask flask-cors RPi.GPIO --break-system-packages
```

### 5. Upload & run stream.py
```bash
# From your laptop:
scp stream.py pi@raspberry.local:/home/pi/

# On the Pi:
python3 stream.py
```

### GPIO Wiring
| Component | BCM Pin |
|-----------|---------|
| Green LED | GPIO 17 |
| Yellow LED | GPIO 27 |
| Red LED | GPIO 22 |
| Buzzer | GPIO 18 |
| SG90 Servo | GPIO 23 |

> Use a 220–330Ω resistor with each LED. Power the servo from the 5V pin.

---

## 💻 Laptop Server Setup

**Requirements:** Anaconda / Miniconda, Python 3.10+, connected to `YUKI` Wi-Fi

### 1. Create Conda environment
```bash
conda create -n crowd_rakshak python=3.10 -y
conda activate crowd_rakshak
```

### 2. Install dependencies
```bash
pip install flask flask-cors opencv-python mediapipe requests
```

### 3. Run the server
```bash
python server.py
```
Open `http://127.0.0.1:5001` in your browser.

> Both Pi and laptop must be on the **same Wi-Fi network (YUKI)**.

---

## 🖥️ Dashboard

| Role | Username | Password | Access |
|------|----------|----------|--------|
| Police | `police` | `police123` | Full — feed, graph, thresholds, manual controls, event log |
| Volunteer | `volunteer` | `volunteer123` | Read-only — feed, status, graph, response guide |

> Change credentials in the `USERS` dict in `server.py` before deployment.

---

## 🔧 Troubleshooting

| Problem | Fix |
|---------|-----|
| `raspberry.local` not found | Check both devices are on YUKI Wi-Fi. Use IP address directly if needed. |
| Camera stream not loading | Make sure `stream.py` is running on Pi. Check camera cable & legacy camera is enabled. |
| Pi hardware not responding | Verify GPIO wiring. Check `stream.py` is reachable on port 5000. |
| `ModuleNotFoundError: mediapipe` | Run `pip install mediapipe` inside the Conda env. Falls back to OpenCV Haar. |
| Blank dashboard page | Ensure `templates/` folder is in the same directory as `server.py`. |

---

## 📡 Auto-start stream.py on Pi boot (optional)

```bash
sudo nano /etc/systemd/system/stream.service
```
```ini
[Unit]
Description=Crowd Rakshak Stream
After=network.target

[Service]
ExecStart=/usr/bin/python3 /home/pi/stream.py
Restart=always
User=pi

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl enable stream.service
sudo systemctl start stream.service
```
