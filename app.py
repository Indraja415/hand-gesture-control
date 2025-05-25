from flask import Flask, render_template, Response, jsonify
from flask_socketio import SocketIO, emit
import cv2
import mediapipe as mp
import base64
import numpy as np
import json
import threading
import time
from collections import deque

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
socketio = SocketIO(app, cors_allowed_origins="*")

class GestureController:
    def __init__(self):
        self.drawing = mp.solutions.drawing_utils
        self.hands = mp.solutions.hands
        self.hand_obj = self.hands.Hands(
            max_num_hands=1,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.5
        )
        self.prev_gesture = -1
        self.start_init = False
        self.start_time = 0
        self.gesture_buffer = deque(maxlen=5)  # Buffer for gesture smoothing
        
    def count_fingers(self, landmarks):
        """Count the number of extended fingers"""
        cnt = 0
        thresh = (landmarks.landmark[0].y * 100 - landmarks.landmark[9].y * 100) / 2
        
        # Check each finger
        if (landmarks.landmark[5].y * 100 - landmarks.landmark[8].y * 100) > thresh:
            cnt += 1  # Index finger
        if (landmarks.landmark[9].y * 100 - landmarks.landmark[12].y * 100) > thresh:
            cnt += 1  # Middle finger
        if (landmarks.landmark[13].y * 100 - landmarks.landmark[16].y * 100) > thresh:
            cnt += 1  # Ring finger
        if (landmarks.landmark[17].y * 100 - landmarks.landmark[20].y * 100) > thresh:
            cnt += 1  # Pinky finger
        
        # Thumb detection (different logic for thumb)
        if landmarks.landmark[4].x < landmarks.landmark[3].x:
            cnt += 1
            
        return cnt
    
    def detect_thumb_gesture(self, landmarks):
        """Detect thumb up/down gestures"""
        thumb_tip_y = landmarks.landmark[4].y
        thumb_base_y = landmarks.landmark[3].y
        
        if thumb_tip_y < thumb_base_y - 0.05:
            return "thumb_up"
        elif thumb_tip_y > thumb_base_y + 0.05:
            return "thumb_down"
        else:
            return "neutral"
    
    def get_gesture_action(self, finger_count, thumb_gesture):
        """Map gestures to video control actions"""
        actions = {
            (0, "neutral"): {"action": "stop", "description": "Stop/Pause"},
            (1, "neutral"): {"action": "play_pause", "description": "Play/Pause"},
            (2, "neutral"): {"action": "volume_up", "description": "Volume Up"},
            (3, "neutral"): {"action": "volume_down", "description": "Volume Down"},
            (4, "neutral"): {"action": "forward", "description": "Seek Forward"},
            (5, "neutral"): {"action": "backward", "description": "Seek Backward"},
            (0, "thumb_up"): {"action": "next_video", "description": "Next Video"},
            (0, "thumb_down"): {"action": "prev_video", "description": "Previous Video"}
        }
        
        key = (finger_count, thumb_gesture)
        return actions.get(key, {"action": "none", "description": "No Action"})
    
    def process_frame(self, frame):
        """Process a single frame and return gesture information"""
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.hand_obj.process(frame_rgb)
        
        gesture_info = {
            "fingers": 0,
            "thumb_gesture": "neutral",
            "action": "none",
            "description": "No hand detected",
            "landmarks": []
        }
        
        if results.multi_hand_landmarks:
            hand_landmarks = results.multi_hand_landmarks[0]
            
            # Count fingers and detect thumb gesture
            finger_count = self.count_fingers(hand_landmarks)
            thumb_gesture = self.detect_thumb_gesture(hand_landmarks)
            
            # Add to gesture buffer for smoothing
            self.gesture_buffer.append((finger_count, thumb_gesture))
            
            # Get most common gesture from buffer
            if len(self.gesture_buffer) >= 3:
                most_common = max(set(self.gesture_buffer), key=self.gesture_buffer.count)
                finger_count, thumb_gesture = most_common
            
            # Get action for gesture
            action_info = self.get_gesture_action(finger_count, thumb_gesture)
            
            # Extract landmarks for drawing
            landmarks = []
            for landmark in hand_landmarks.landmark:
                landmarks.append({
                    "x": landmark.x,
                    "y": landmark.y,
                    "z": landmark.z
                })
            
            gesture_info = {
                "fingers": finger_count,
                "thumb_gesture": thumb_gesture,
                "action": action_info["action"],
                "description": action_info["description"],
                "landmarks": landmarks
            }
            
            # Draw landmarks on frame
            self.drawing.draw_landmarks(frame, hand_landmarks, self.hands.HAND_CONNECTIONS)
        
        return frame, gesture_info

# Global gesture controller
gesture_controller = GestureController()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/demo')
def demo():
    return render_template('demo.html')

@socketio.on('video_frame')
def handle_video_frame(data):
    try:
        # Decode base64 image
        image_data = base64.b64decode(data['image'].split(',')[1])
        nparr = np.frombuffer(image_data, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if frame is not None:
            # Process frame for gesture recognition
            processed_frame, gesture_info = gesture_controller.process_frame(frame)
            
            # Encode processed frame back to base64
            _, buffer = cv2.imencode('.jpg', processed_frame)
            processed_image = base64.b64encode(buffer).decode()
            
            # Send back processed frame and gesture info
            emit('processed_frame', {
                'image': f"data:image/jpeg;base64,{processed_image}",
                'gesture': gesture_info
            })
    except Exception as e:
        print(f"Error processing frame: {e}")
        emit('error', {'message': str(e)})

@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
