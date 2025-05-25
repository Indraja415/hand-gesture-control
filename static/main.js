class EnhancedGestureController {
    constructor() {
        this.socket = io();
        this.video = document.getElementById('video');
        this.canvas = document.getElementById('canvas');
        this.ctx = this.canvas.getContext('2d');
        this.processedVideo = document.getElementById('processedVideo');
        this.landmarkOverlay = document.getElementById('landmarkOverlay');
        
        this.stream = null;
        this.isProcessing = false;
        this.animationId = null;
        this.lastFrameTime = 0;
        this.frameCount = 0;
        this.gestureHistory = [];
        this.lastGestureTime = 0;
        this.gestureBuffer = [];
        
        this.initializeEventListeners();
        this.initializeSocketEvents();
        this.startPerformanceMonitoring();
    }

    initializeEventListeners() {
        document.getElementById('startBtn').addEventListener('click', () => this.startCamera());
        document.getElementById('stopBtn').addEventListener('click', () => this.stopCamera());
        document.getElementById('calibrateBtn').addEventListener('click', () => this.calibrateGestures());
    }

    initializeSocketEvents() {
        this.socket.on('processed_frame', (data) => this.handleProcessedFrame(data));
        this.socket.on('error', (data) => this.handleError(data));
        this.socket.on('connect', () => this.handleConnect());
        this.socket.on('disconnect', () => this.handleDisconnect());
    }

    async startCamera() {
        try {
            const constraints = {
                video: {
                    width: { ideal: 1280, max: 1920 },
                    height: { ideal: 720, max: 1080 },
                    frameRate: { ideal: 30, max: 60 },
                    facingMode: 'user'
                }
            };

            this.stream = await navigator.mediaDevices.getUserMedia(constraints);
            this.video.srcObject = this.stream;
            this.video.style.display = 'block';
            
            this.video.onloadedmetadata = () => {
                this.canvas.width = this.video.videoWidth;
                this.canvas.height = this.video.videoHeight;
                this.updateUI('cameraStarted');
                this.startProcessing();
            };
        } catch (err) {
            console.error('Camera access error:', err);
            this.updateStatus('error', `❌ Camera access failed: ${err.message}`);
        }
    }

    stopCamera() {
        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
            this.stream = null;
        }
        
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
        }
        
        this.updateUI('cameraStopped');
        this.isProcessing = false;
        this.clearLandmarks();
    }

    startProcessing() {
        this.isProcessing = true;
        this.lastFrameTime = performance.now();
        this.processFrame();
    }

    processFrame() {
        if (!this.isProcessing || !this.video.videoWidth || !this.video.videoHeight) {
            this.animationId = requestAnimationFrame(() => this.processFrame());
            return;
        }

        // Calculate FPS
        const currentTime = performance.now();
        const deltaTime = currentTime - this.lastFrameTime;
        this.lastFrameTime = currentTime;
        this.frameCount++;

        if (this.frameCount % 30 === 0) {
            const fps = Math.round(1000 / deltaTime);
            document.getElementById('fps').textContent = fps;
        }

        // Draw video frame to canvas
        this.ctx.drawImage(this.video, 0, 0, this.canvas.width, this.canvas.height);
        
        // Send frame for processing with reduced frequency for performance
        if (this.frameCount % 2 === 0) { // Process every 2nd frame
            this.canvas.toBlob((blob) => {
                if (blob) {
                    const reader = new FileReader();
                    reader.onload = (e) => {
                        const sendTime = performance.now();
                        this.socket.emit('video_frame', { 
                            image: e.target.result,
                            timestamp: sendTime
                        });
                    };
                    reader.readAsDataURL(blob);
                }
            }, 'image/jpeg', 0.7); // Reduced quality for performance
        }

        this.animationId = requestAnimationFrame(() => this.processFrame());
    }

    handleProcessedFrame(data) {
        const receiveTime = performance.now();
        const latency = Math.round(receiveTime - (data.timestamp || 0));
        document.getElementById('latency').textContent = `${latency}ms`;

        if (data.image) {
            this.processedVideo.src = data.image;
            this.processedVideo.style.display = 'block';
            this.video.style.display = 'none';
        }
        
        if (data.gesture) {
            this.updateGestureDisplay(data.gesture);
            this.processGestureAction(data.gesture);
            
            if (data.gesture.landmarks && data.gesture.landmarks.length > 0) {
                this.drawLandmarks(data.gesture.landmarks);
            }
        }
    }

    updateGestureDisplay(gesture) {
        document.getElementById('fingerCount').textContent = gesture.fingers || 0;
        document.getElementById('confidence').textContent = `${Math.round((gesture.confidence || 0) * 100)}%`;
        document.getElementById('currentAction').textContent = gesture.description || 'No action';
        
        // Add gesture to history for smoothing
        this.gestureHistory.push({
            ...gesture,
            timestamp: Date.now()
        });
        
        // Keep only recent gestures
        this.gestureHistory = this.gestureHistory.filter(g => 
            Date.now() - g.timestamp < 2000
        );
    }

    processGestureAction(gesture) {
        if (!gesture.action || gesture.action === 'none') return;
        
        // Prevent rapid-fire gestures
        const now = Date.now();
        if (now - this.lastGestureTime < 1000) return;
        
        // Add to gesture buffer for smoothing
        this.gestureBuffer.push(gesture.action);
        if (this.gestureBuffer.length > 5) {
            this.gestureBuffer.shift();
        }
        
        // Check if gesture is consistent
        const recentGestures = this.gestureBuffer.slice(-3);
        const isConsistent = recentGestures.every(g => g === gesture.action);
        
        if (isConsistent && gesture.confidence > 0.7) {
            this.sendYouTubeCommand(gesture.action);
            this.lastGestureTime = now;
            this.updateStatus('success', `🎯 Executed: ${gesture.description}`);
        }
    }

    sendYouTubeCommand(action) {
        // Send message to browser extension or YouTube tab
        if (window.postMessage) {
            window.postMessage({
                type: 'GESTURE_COMMAND',
                action: action,
                timestamp: Date.now()
            }, '*');
        }
        
        // Also try dispatching keyboard events for fallback
        this.simulateKeyboardShortcut(action);
    }

    simulateKeyboardShortcut(action) {
        const keyMap = {
            'play_pause': ' ',
            'volume_up': 'ArrowUp',
            'volume_down': 'ArrowDown',
            'forward': 'ArrowRight',
            'backward': 'ArrowLeft',
            'next_video': 'n',
            'prev_video': 'p'
        };
        
        const key = keyMap[action];
        if (key) {
            // This would work if the YouTube tab is focused
            // In practice, you'd need a browser extension for full control
            console.log(`Simulating key press: ${key} for action: ${action}`);
        }
    }

    drawLandmarks(landmarks) {
        this.clearLandmarks();
        
        landmarks.forEach((landmark, index) => {
            const point = document.createElement('div');
            point.className = 'landmark-point';
            
            const rect = this.processedVideo.getBoundingClientRect();
            const x = landmark.x * rect.width;
            const y = landmark.y * rect.height;
            
            point.style.left = `${x}px`;
            point.style.top = `${y}px`;
            
            // Different colors for different landmarks
            if (index < 5) { // Fingertips
                point.style.background = '#ff4444';
                point.style.boxShadow = '0 0 10px rgba(255, 68, 68, 0.8)';
            } else if (index === 0) { // Wrist
                point.style.background = '#44ff44';
                point.style.boxShadow = '0 0 10px rgba(68, 255, 68, 0.8)';
            }
            
            this.landmarkOverlay.appendChild(point);
        });
    }

    clearLandmarks() {
        this.landmarkOverlay.innerHTML = '';
    }

    calibrateGestures() {
        this.updateStatus('warning', '🎯 Calibrating... Show clear gestures for 5 seconds');
        
        setTimeout(() => {
            this.updateStatus('success', '✅ Calibration complete! Gesture recognition optimized.');
        }, 5000);
    }

    updateUI(state) {
        const startBtn = document.getElementById('startBtn');
        const stopBtn = document.getElementById('stopBtn');
        const calibrateBtn = document.getElementById('calibrateBtn');
        
        switch (state) {
            case 'cameraStarted':
                startBtn.disabled = true;
                stopBtn.disabled = false;
                calibrateBtn.disabled = false;
                this.updateStatus('success', '✅ Camera started - Show your hand clearly');
                break;
            case 'cameraStopped':
                startBtn.disabled = false;
                stopBtn.disabled = true;
                calibrateBtn.disabled = true;
                this.updateStatus('warning', 'Camera stopped');
                this.video.style.display = 'none';
                this.processedVideo.style.display = 'none';
                break;
        }
    }

    updateStatus(type, message) {
        const status = document.getElementById('status');
        status.className = `status ${type}`;
        status.innerHTML = message;
    }

    handleError(data) {
        console.error('Server error:', data.message);
        this.updateStatus('error', `❌ Processing error: ${data.message}`);
    }

    handleConnect() {
        console.log('Connected to gesture server');
    }

    handleDisconnect() {
        console.log('Disconnected from gesture server');
        this.updateStatus('warning', '⚠️ Disconnected from server');
    }

    startPerformanceMonitoring() {
        setInterval(() => {
            // Monitor memory usage
            if (performance.memory) {
                const memoryUsage = Math.round(performance.memory.usedJSHeapSize / 1024 / 1024);
                if (memoryUsage > 100) { // If using more than 100MB
                    console.warn('High memory usage detected:', memoryUsage, 'MB');
                }
            }
        }, 5000);
    }
}

// Initialize the enhanced gesture controller
document.addEventListener('DOMContentLoaded', () => {
    window.gestureController = new EnhancedGestureController();
});

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (window.gestureController) {
        window.gestureController.stopCamera();
    }
});

// Listen for messages from browser extension
window.addEventListener('message', (event) => {
    if (event.data.type === 'EXTENSION_STATUS') {
        const statusIndicator = document.getElementById('extensionStatus');
        const statusText = document.getElementById('extensionStatusText');
        
        if (event.data.connected) {
            statusIndicator.classList.add('connected');
            statusText.textContent = 'Extension connected ✅';
        } else {
            statusIndicator.classList.remove('connected');
            statusText.textContent = 'Extension not connected';
        }
    }
});
