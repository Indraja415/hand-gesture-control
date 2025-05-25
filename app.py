from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import cv2
import numpy as np
import mediapipe as mp
import base64
import io
from PIL import Image
import time
import threading
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
app.run(host='0.0.0.0', port=5000, debug=True)

class GestureRecognizer:
    def __init__(self):
        # Initialize MediaPipe hands
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.5
        )
        self.mp_draw = mp.solutions.drawing_utils
        
        # Gesture mapping
        self.gesture_actions = {
            1: {'action': 'play_pause', 'description': '▶️ Play/Pause'},
            2: {'action': 'volume_up', 'description': '🔊 Volume Up'},
            3: {'action': 'volume_down', 'description': '🔉 Volume Down'},
            4: {'action': 'forward', 'description': '⏩ Skip Forward 10s'},
            5: {'action': 'backward', 'description': '⏪ Skip Backward 10s'},
        }
        
        # Special gestures
        self.special_gestures = {
            'thumbs_up': {'action': 'next_video', 'description': '⏭️ Next Video'},
            'thumbs_down': {'action': 'prev_video', 'description': '⏮️ Previous Video'},
            'fist': {'action': 'stop', 'description': '⏹️ Full Stop'}
        }
        
    def count_fingers(self, landmarks):
        """Count the number of extended fingers"""
        tip_ids = [4, 8, 12, 16, 20]  # Thumb, Index, Middle, Ring, Pinky
        fingers = []
        
        # Thumb (different logic due to orientation)
        if landmarks[tip_ids[0]].x > landmarks[tip_ids[0] - 1].x:
            fingers.append(1)
        else:
            fingers.append(0)
            
        # Other four fingers
        for id in range(1, 5):
            if landmarks[tip_ids[id]].y < landmarks[tip_ids[id] - 2].y:
                fingers.append(1)
            else:
                fingers.append(0)
                
        return fingers, sum(fingers)
    
    def detect_special_gestures(self, landmarks):
        """Detect special gestures like thumbs up, thumbs down, fist"""
        # Get landmark positions
        thumb_tip = landmarks[4]
        thumb_ip = landmarks[3]
        index_tip = landmarks[8]
        middle_tip = landmarks[12]
        ring_tip = landmarks[16]
        pinky_tip = landmarks[20]
        
        # Thumbs up detection
        thumb_up = thumb_tip.y < thumb_ip.y
        fingers_down = (index_tip.y > landmarks[6].y and 
                       middle_tip.y > landmarks[10].y and
                       ring_tip.y > landmarks[14].y and
                       pinky_tip.y > landmarks[18].y)
        
        if thumb_up and fingers_down:
            return 'thumbs_up'
            
        # Thumbs down detection
        thumb_down = thumb_tip.y > thumb_ip.y
        if thumb_down and fingers_down:
            return 'thumbs_down'
            
        # Fist detection (all fingers closed)
        all_fingers_down = (index_tip.y > landmarks[6].y and 
                           middle_tip.y > landmarks[10].y and
                           ring_tip.y > landmarks[14].y and
                           pinky_tip.y > landmarks[18].y and
                           thumb_tip.x < landmarks[2].x)
        
        if all_fingers_down:
            return 'fist'
            
        return None
    
    def process_frame(self, image):
        """Process a single frame and return gesture information"""
        try:
            # Convert image to RGB
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            results = self.hands.process(rgb_image)
            
            gesture_info = {
                'fingers': 0,
                'confidence': 0,
                'action': 'none',
                'description': 'No gesture detected',
                'landmarks': []
            }
            
            if results.multi_hand_landmarks:
                for hand_landmarks in results.multi_hand_landmarks:
                    # Draw landmarks on image
                    self.mp_draw.draw_landmarks(
                        image, hand_landmarks, self.mp_hands.HAND_CONNECTIONS)
                    
                    # Extract landmark coordinates
                    landmarks = []
                    for lm in hand_landmarks.landmark:
                        landmarks.append({'x': lm.x, 'y': lm.y, 'z': lm.z})
                    
                    gesture_info['landmarks'] = landmarks
                    
                    # Count fingers
                    fingers, finger_count = self.count_fingers(hand_landmarks.landmark)
                    gesture_info['fingers'] = finger_count
                    
                    # Calculate confidence (simplified)
                    gesture_info['confidence'] = 0.9  # You can implement actual confidence calculation
                    
                    # Detect special gestures first
                    special_gesture = self.detect_special_gestures(hand_landmarks.landmark)
                    
                    if special_gesture and special_gesture in self.special_gestures:
                        gesture_info.update(self.special_gestures[special_gesture])
                    elif finger_count in self.gesture_actions:
                        gesture_info.update(self.gesture_actions[finger_count])
                    else:
                        gesture_info['description'] = f'{finger_count} fingers detected'
            
            return image, gesture_info
            
        except Exception as e:
            logger.error(f"Error processing frame: {str(e)}")
            return image, {
                'fingers': 0,
                'confidence': 0,
                'action': 'error',
                'description': f'Processing error: {str(e)}',
                'landmarks': []
            }

# Initialize gesture recognizer
gesture_recognizer = GestureRecognizer()

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    logger.info('Client connected')
    emit('status', {'message': 'Connected to gesture recognition server'})

@socketio.on('disconnect')
def handle_disconnect():
    logger.info('Client disconnected')

@socketio.on('video_frame')
def handle_video_frame(data):
    try:
        # Decode base64 image
        image_data = data['image'].split(',')[1]  # Remove data:image/jpeg;base64,
        image_bytes = base64.b64decode(image_data)
        
        # Convert to numpy array
        nparr = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            emit('error', {'message': 'Failed to decode image'})
            return
        
        # Process the frame
        processed_image, gesture_info = gesture_recognizer.process_frame(image)
        
        # Encode processed image back to base64
        _, buffer = cv2.imencode('.jpg', processed_image, [cv2.IMWRITE_JPEG_QUALITY, 80])
        processed_image_b64 = base64.b64encode(buffer).decode('utf-8')
        processed_image_data_url = f"data:image/jpeg;base64,{processed_image_b64}"
        
        # Send processed frame and gesture info back to client
        emit('processed_frame', {
            'image': processed_image_data_url,
            'gesture': gesture_info,
            'timestamp': data.get('timestamp', time.time() * 1000)
        })
        
    except Exception as e:
        logger.error(f"Error handling video frame: {str(e)}")
        emit('error', {'message': f'Frame processing error: {str(e)}'})

@socketio.on('calibrate')
def handle_calibrate():
    """Handle calibration request"""
    try:
        # Simulate calibration process
        emit('status', {'message': 'Calibration started...'})
        
        # In a real implementation, you might:
        # - Collect baseline measurements
        # - Adjust detection thresholds
        # - Train user-specific gesture models
        
        time.sleep(2)  # Simulate calibration time
        emit('status', {'message': 'Calibration completed successfully!'})
        
    except Exception as e:
        logger.error(f"Calibration error: {str(e)}")
        emit('error', {'message': f'Calibration failed: {str(e)}'})

if __name__ == '__main__':
    print("🚀 Starting Enhanced Gesture Recognition Server...")
    print("📡 Server will be available at: http://localhost:5000")
    print("🖐️ Make sure you have the required dependencies installed:")
    print("   pip install flask flask-socketio opencv-python mediapipe pillow")
    
    try:
        socketio.run(app, host='0.0.0.0', port=5000, debug=True)
    except Exception as e:
        print(f"❌ Failed to start server: {str(e)}")
        print("💡 Make sure port 5000 is available and try again.")
