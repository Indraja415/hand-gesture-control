from flask import Flask, render_template, Response, jsonify
import cv2
import mediapipe as mp
import time
import os

app = Flask(__name__)

# Check if we're in a web deployment environment
IS_WEB_DEPLOY = os.environ.get('PORT') is not None or 'DISPLAY' not in os.environ

# Only import pyautogui for local development
if not IS_WEB_DEPLOY:
    try:
        import pyautogui
        pyautogui.FAILSAFE = False
        print("Running in LOCAL mode - PyAutoGUI enabled")
    except ImportError:
        IS_WEB_DEPLOY = True
        print("PyAutoGUI not available - Web mode enabled")
else:
    print("Running in WEB DEPLOYMENT mode - PyAutoGUI disabled")

# Initialize MediaPipe
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(max_num_hands=1, min_detection_confidence=0.7)
mp_draw = mp.solutions.drawing_utils

# Initialize camera only if not in web deployment
cap = None
if not IS_WEB_DEPLOY:
    try:
        cap = cv2.VideoCapture(0)
    except Exception as e:
        print(f"Camera initialization failed: {e}")
        IS_WEB_DEPLOY = True

# Helper to count fingers
def count_fingers(hand_landmarks):
    fingers = []
    # Thumb
    if hand_landmarks.landmark[4].x > hand_landmarks.landmark[3].x:
        fingers.append(1)
    else:
        fingers.append(0)
    # Other fingers
    for tip_id in [8, 12, 16, 20]:
        if hand_landmarks.landmark[tip_id].y < hand_landmarks.landmark[tip_id - 2].y:
            fingers.append(1)
        else:
            fingers.append(0)
    return sum(fingers)

last_action_time = 0
cooldown = 1.5  # seconds

def gen_frames():
    global last_action_time
    
    # If in web deployment mode, return demo frames
    if IS_WEB_DEPLOY or cap is None:
        while True:
            # Create a simple demo frame
            demo_frame = create_demo_frame()
            ret, buffer = cv2.imencode('.jpg', demo_frame)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            time.sleep(0.1)  # Control frame rate
    
    else:
        # Local mode with actual camera
        while True:
            success, frame = cap.read()
            if not success:
                break
            
            frame = cv2.flip(frame, 1)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = hands.process(rgb)
            
            finger_count = 0
            if results.multi_hand_landmarks:
                for hand_landmarks in results.multi_hand_landmarks:
                    mp_draw.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)
                    finger_count = count_fingers(hand_landmarks)
                    
                    current_time = time.time()
                    if current_time - last_action_time > cooldown:
                        if finger_count == 1:
                            pyautogui.press('space')
                            print("Play/Pause")
                        elif finger_count == 2:
                            pyautogui.press('up')
                            print("Volume Up")
                        elif finger_count == 3:
                            pyautogui.press('down')
                            print("Volume Down")
                        elif finger_count == 4:
                            pyautogui.press('left')
                            print("Backward")
                        elif finger_count == 5:
                            pyautogui.press('right')
                            print("Forward")
                        elif finger_count == 0:
                            pyautogui.hotkey('shift', 'n')
                            print("Next Video")
                        last_action_time = current_time
            
            cv2.putText(frame, f'Fingers: {finger_count}', (10, 70),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
            
            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

def create_demo_frame():
    """Create a demo frame for web deployment"""
    import numpy as np
    
    # Create a black frame
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    
    # Add text explaining the demo mode
    text_lines = [
        "HAND GESTURE CONTROL - DEMO MODE",
        "",
        "This is running in web deployment mode.",
        "Camera and gesture controls are disabled.",
        "",
        "To use full functionality:",
        "1. Download the code",
        "2. Run locally: python app.py",
        "3. Allow camera access",
        "",
        "Gesture Controls (Local Mode Only):",
        "1 finger = Play/Pause",
        "2 fingers = Volume Up",
        "3 fingers = Volume Down",
        "4 fingers = Backward",
        "5 fingers = Forward",
        "Fist (0 fingers) = Next Video"
    ]
    
    y_start = 30
    for i, line in enumerate(text_lines):
        y_pos = y_start + (i * 25)
        if y_pos > 450:  # Don't go beyond frame
            break
        cv2.putText(frame, line, (20, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 
                   0.5, (0, 255, 255), 1)
    
    return frame

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video')
def video():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/status')
def status():
    """API endpoint to check deployment mode"""
    return jsonify({
        'mode': 'web_deploy' if IS_WEB_DEPLOY else 'local',
        'pyautogui_available': not IS_WEB_DEPLOY,
        'camera_available': cap is not None and not IS_WEB_DEPLOY
    })

@app.route('/health')
def health():
    """Health check for deployment"""
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug_mode = not IS_WEB_DEPLOY
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
