// DOM elements
const videoFeed = document.getElementById('videoFeed');
const loading = document.getElementById('loading');
const status = document.getElementById('status');

// Show loading initially
loading.style.display = 'block';

// Video feed event handlers
videoFeed.addEventListener('load', function() {
    loading.style.display = 'none';
    updateStatus('🟢 Live', 'success');
});

videoFeed.addEventListener('error', function() {
    loading.style.display = 'none';
    updateStatus('🔴 Error', 'error');
    showErrorMessage();
});

// Status update function
function updateStatus(text, type) {
    status.textContent = text;
    const statusIndicator = document.querySelector('.status-indicator');
    
    // Remove existing status classes
    statusIndicator.classList.remove('status-success', 'status-error', 'status-warning');
    
    // Add appropriate status class
    if (type === 'success') {
        statusIndicator.classList.add('status-success');
    } else if (type === 'error') {
        statusIndicator.classList.add('status-error');
    } else if (type === 'warning') {
        statusIndicator.classList.add('status-warning');
    }
}

// Error message display
function showErrorMessage() {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-message';
    errorDiv.innerHTML = `
        <h3>Camera Error</h3>
        <p>Unable to connect to camera feed. Please check:</p>
        <ul>
            <li>Camera permissions are granted</li>
            <li>Camera is not being used by another application</li>
            <li>Flask server is running</li>
        </ul>
        <button onclick="reloadPage()">Retry</button>
    `;
    
    const videoContainer = document.querySelector('.video-container');
    videoContainer.appendChild(errorDiv);
}

// Page reload function
function reloadPage() {
    window.location.reload();
}

// Add gesture highlighting effect
document.addEventListener('DOMContentLoaded', function() {
    const gestureItems = document.querySelectorAll('.gesture-item');
    
    // Add hover effect for better interactivity
    gestureItems.forEach((item, index) => {
        item.addEventListener('mouseenter', function() {
            this.style.transform = 'translateX(10px) scale(1.02)';
        });
        
        item.addEventListener('mouseleave', function() {
            this.style.transform = 'translateX(0) scale(1)';
        });
        
        // Stagger animation delays
        item.style.animationDelay = `${0.1 * (index + 1)}s`;
    });
});

// Keyboard shortcuts info
document.addEventListener('keydown', function(e) {
    if (e.key === '?' || (e.shiftKey && e.key === '/')) {
        showKeyboardShortcuts();
    }
});

// Show keyboard shortcuts modal
function showKeyboardShortcuts() {
    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.innerHTML = `
        <div class="modal-content">
            <span class="close">&times;</span>
            <h2>Keyboard Shortcuts</h2>
            <div class="shortcuts-list">
                <div class="shortcut-item">
                    <span class="key">Space</span>
                    <span class="action">Play/Pause</span>
                </div>
                <div class="shortcut-item">
                    <span class="key">↑</span>
                    <span class="action">Volume Up</span>
                </div>
                <div class="shortcut-item">
                    <span class="key">↓</span>
                    <span class="action">Volume Down</span>
                </div>
                <div class="shortcut-item">
                    <span class="key">←</span>
                    <span class="action">Backward</span>
                </div>
                <div class="shortcut-item">
                    <span class="key">→</span>
                    <span class="action">Forward</span>
                </div>
                <div class="shortcut-item">
                    <span class="key">Shift + N</span>
                    <span class="action">Next Video</span>
                </div>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    // Close modal functionality
    modal.querySelector('.close').addEventListener('click', function() {
        document.body.removeChild(modal);
    });
    
    modal.addEventListener('click', function(e) {
        if (e.target === modal) {
            document.body.removeChild(modal);
        }
    });
}

// Connection monitoring
let connectionCheckInterval;

function startConnectionMonitoring() {
    connectionCheckInterval = setInterval(checkConnection, 5000);
}

function checkConnection() {
    fetch('/video', { method: 'HEAD' })
        .then(response => {
            if (response.ok) {
                updateStatus('🟢 Live', 'success');
            } else {
                updateStatus('🟡 Reconnecting...', 'warning');
            }
        })
        .catch(() => {
            updateStatus('🔴 Disconnected', 'error');
        });
}

// Performance monitoring
let frameCount = 0;
let lastFrameTime = Date.now();

function trackPerformance() {
    frameCount++;
    const currentTime = Date.now();
    
    if (currentTime - lastFrameTime >= 1000) {
        const fps = frameCount;
        frameCount = 0;
        lastFrameTime = currentTime;
        
        // Update performance indicator if needed
        if (fps < 15) {
            updateStatus('🟡 Low Performance', 'warning');
        }
    }
}

// Initialize monitoring when page loads
window.addEventListener('load', function() {
    startConnectionMonitoring();
    
    // Add performance tracking
    if (videoFeed.complete) {
        setInterval(trackPerformance, 100);
    }
});

// Cleanup on page unload
window.addEventListener('beforeunload', function() {
    if (connectionCheckInterval) {
        clearInterval(connectionCheckInterval);
    }
});

// Add touch support for mobile devices
if ('ontouchstart' in window) {
    document.body.classList.add('touch-device');
    
    // Add touch event listeners for gesture items
    const gestureItems = document.querySelectorAll('.gesture-item');
    gestureItems.forEach(item => {
        item.addEventListener('touchstart', function() {
            this.style.transform = 'translateX(5px) scale(1.02)';
        });
        
        item.addEventListener('touchend', function() {
            this.style.transform = 'translateX(0) scale(1)';
        });
    });
}

// Fullscreen functionality
function toggleFullscreen() {
    if (!document.fullscreenElement) {
        document.documentElement.requestFullscreen();
    } else {
        document.exitFullscreen();
    }
}

// Add fullscreen button if supported
if (document.fullscreenEnabled) {
    const fullscreenBtn = document.createElement('button');
    fullscreenBtn.className = 'fullscreen-btn';
    fullscreenBtn.innerHTML = '⛶';
    fullscreenBtn.title = 'Toggle Fullscreen';
    fullscreenBtn.addEventListener('click', toggleFullscreen);
    
    document.querySelector('.video-container').appendChild(fullscreenBtn);
}