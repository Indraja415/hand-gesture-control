from flask import Flask, render_template, Response
import cv2
import mediapipe as mp
import pyautogui
import time

app = Flask(__name__)

# Initialize MediaPipe
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(max_num_hands=1, min_detection_confidence=0.7)
mp_draw = mp.solutions.drawing_utils

cap = cv2.VideoCapture(0)

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
    while True:
        success, frame = cap.read()
        if not success:
            break

        frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = hands.process(rgb)

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

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video')
def video():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    app.run(debug=True)