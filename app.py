#!/usr/bin/env python3
"""
Enhanced Hand Gesture Video Control Backend
Main Flask server with Socket.IO support
"""

import os
import cv2
import base64
import numpy as np
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
import mediapipe as mp
import time
import logging
from typing import Dict, List, Tuple, Optional
import json
from dataclasses import dataclass, asdict
from threading import Lock
import asyncio

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Initialize MediaPipe
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles

@dataclass
class GestureResult:
    """Data class for gesture recognition results"""
    fingers: int
    confidence: float
    action: str
    description: str
    landmarks: List[Dict]
    gesture_name: str

class EnhancedGestureRecognizer:
    """Enhanced gesture recognition with improved accuracy and stability"""
    
    def __init__(self):
        self.hands = mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.5,
            model_complexity=1
        )
        
        self.gesture_history = []
        self.gesture_lock = Lock()
        self.last_gesture_time = 0
        self.gesture_cooldown = 0.5  # 500ms cooldown between gestures
        
        # Finger tip and PIP joint indices for MediaPipe
        self.finger_tips = [4, 8, 12, 16, 20]  # Thumb, Index, Middle, Ring, Pinky
        self.finger_pips = [3, 6, 10, 14, 18]  # PIP joints
        self.finger_mcp = [2, 5, 9, 13, 17]   # MCP joints
        
    def count_fingers(self, landmarks) -> Tuple[int, List[bool]]:
        """Count extended fingers with improved accuracy"""
        finger_states = [False] * 5
        
        # Thumb (special case - check x-coordinate relative to MCP)
        if landmarks[self.finger_tips[0]].x > landmarks[self.finger_mcp[0]].x:
            finger_states[0] = True
        
        # Other fingers (check y-coordinate)
        for i in range(1, 5):
            if landmarks[self.finger_tips[i]].y < landmarks[self.finger_pips[i]].y:
                finger_states[i] = True
        
        return sum(finger_states), finger_states
    
    def detect_special_gestures(self, landmarks) -> Optional[str]:
        """Detect special gestures like thumbs up/down, fist, etc."""
        finger_count, finger_states = self.count_fingers(landmarks)
        
        # Thumbs up detection
        thumb_up = (finger_states[0] and not any(finger_states[1:]) and
                   landmarks[self.finger_tips[0]].y < landmarks[self.finger_mcp[0]].y)
        
        if thumb_up:
            return "thumbs_up"
        
        # Thumbs down detection  
        thumb_down = (finger_states[0] and not any(finger_states[1:]) and
                     landmarks[self.finger_tips[0]].y > landmarks[self.finger_mcp[0]].y)
        
        if thumb_down:
            return "thumbs_down"
        
        # Fist detection (all fingers closed)
        if finger_count == 0:
            return "fist"
        
        # Peace sign (index and middle finger)
        if finger_count == 2 and finger_states[1] and finger_states[2]:
            return "peace"
            
        return None
    
    def calculate_gesture_confidence(self, landmarks) -> float:
        """Calculate confidence based on hand stability and visibility"""
        # Check landmark visibility scores
        visibility_scores = [lm.visibility if hasattr(lm, 'visibility') else 1.0 for lm in landmarks]
        avg_visibility = sum(visibility_scores) / len(visibility_scores)
        
        # Check hand stability (distance between consecutive frames)
        stability_score = 1.0  # Simplified for now
        
        return min(avg_visibility * stability_score, 1.0)
    
    def map_gesture_to_action(self, finger_count: int, special_gesture: str) -> Tuple[str, str]:
        """Map detected gesture to YouTube action"""
        action_map = {
            1: ("play_pause", "▶️ Play/Pause"),
            2: ("volume_up", "🔊 Volume Up"), 
            3: ("volume_down", "🔉 Volume Down"),
            4: ("forward", "⏩ Skip Forward 10s"),
            5: ("backward", "⏪ Skip Backward 10s"),
        }
        
        special_action_map = {
            "thumbs_up": ("next_video", "⏭️ Next Video"),
            "thumbs_down": ("prev_video", "⏮️ Previous Video"),
            "fist": ("stop", "⏹️ Full Stop"),
            "peace": ("volume_up", "🔊 Volume Up")
        }
        
        if special_gesture and special_gesture in special_action_map:
            return special_action_map[special_gesture]
        elif finger_count in action_map:
            return action_map[finger_count]
        else:
            return ("none", "No action")
    
    def process_frame(self, frame: np.ndarray) -> Tuple[np.ndarray, Optional[GestureResult]]:
        """Process a single frame and return annotated frame with gesture result"""
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.hands.process(rgb_frame)
        
        annotated_frame = frame.copy()
        gesture_result = None
        
        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                # Draw hand landmarks
                mp_drawing.draw_landmarks(
                    annotated_frame,
                    hand_landmarks,
                    mp_hands.HAND_CONNECTIONS,
                    mp_drawing_styles.get_default_hand_landmarks_style(),
                    mp_drawing_styles.get_default_hand_connections_style()
                )
                
                # Extract landmark coordinates
                landmarks_list = []
                for lm in hand_landmarks.landmark:
                    landmarks_list.append({
                        'x': lm.x,
                        'y': lm.y,
                        'z': lm.z
                    })
                
                # Analyze gesture
                finger_count, finger_states = self.count_fingers(hand_landmarks.landmark)
                special_gesture = self.detect_special_gestures(hand_landmarks.landmark)
                confidence = self.calculate_gesture_confidence(hand_landmarks.landmark)
                
                # Map to action
                action, description = self.map_gesture_to_action(finger_count, special_gesture)
                gesture_name = special_gesture or f"{finger_count}_fingers"
                
                # Create gesture result
                gesture_result = GestureResult(
                    fingers=finger_count,
                    confidence=confidence,
                    action=action,
                    description=description,
                    landmarks=landmarks_list,
                    gesture_name=gesture_name
                )
                
                # Add text overlay
                cv2.putText(annotated_frame, f"Fingers: {finger_count}", 
                           (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                cv2.putText(annotated_frame, f"Action: {description}", 
                           (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
                cv2.putText(annotated_frame, f"Confidence: {confidence:.2f}", 
                           (10, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        
        return annotated_frame, gesture_result

# Global gesture recognizer instance
gesture_recognizer = EnhancedGestureRecognizer()

@app.route('/')
def index():
    """Serve the main HTML page"""
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    logger.info(f"Client connected: {request.sid}")
    emit('status', {'message': 'Connected to gesture recognition server'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    logger.info(f"Client disconnected: {request.sid}")

@socketio.on('video_frame')
def handle_video_frame(data):
    """Process incoming video frame"""
    try:
        # Decode base64 image
        image_data = data['image'].split(',')[1]  # Remove data:image/jpeg;base64,
        image_bytes = base64.b64decode(image_data)
        
        # Convert to numpy array
        nparr = np.frombuffer(image_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if frame is None:
            emit('error', {'message': 'Failed to decode image'})
            return
        
        # Process frame
        start_time = time.time()
        annotated_frame, gesture_result = gesture_recognizer.process_frame(frame)
        processing_time = (time.time() - start_time) * 1000  # Convert to ms
        
        # Encode processed frame
        _, buffer = cv2.imencode('.jpg', annotated_frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        processed_image = base64.b64encode(buffer).decode('utf-8')
        processed_image_url = f"data:image/jpeg;base64,{processed_image}"
        
        # Prepare response
        response_data = {
            'image': processed_image_url,
            'timestamp': data.get('timestamp', time.time() * 1000),
            'processing_time': processing_time
        }
        
        if gesture_result:
            response_data['gesture'] = asdict(gesture_result)
        
        emit('processed_frame', response_data)
        
    except Exception as e:
        logger.error(f"Error processing frame: {str(e)}")
        emit('error', {'message': f'Frame processing error: {str(e)}'})

@socketio.on('calibrate')
def handle_calibration():
    """Handle gesture calibration request"""
    try:
        # Reset gesture history and recalibrate
        with gesture_recognizer.gesture_lock:
            gesture_recognizer.gesture_history.clear()
        
        emit('status', {'message': 'Calibration started - show clear gestures'})
        
        # Simulate calibration process
        socketio.sleep(3)
        emit('status', {'message': 'Calibration complete'})
        
    except Exception as e:
        logger.error(f"Calibration error: {str(e)}")
        emit('error', {'message': f'Calibration failed: {str(e)}'})

@app.errorhandler(404)
def not_found(error):
    return {'error': 'Endpoint not found'}, 404

@app.errorhandler(500)
def internal_error(error):
    return {'error': 'Internal server error'}, 500

if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    if not os.path.exists('templates'):
        os.makedirs('templates')
    
    # Run the application
    logger.info("Starting Enhanced Gesture Recognition Server...")
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
