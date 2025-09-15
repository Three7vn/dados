// Dados Web UI JavaScript
// Connects to WebSocket for real-time updates from the voice agent

document.addEventListener('DOMContentLoaded', function() {
    const startBtn = document.getElementById('startBtn');
    const speechBox = document.getElementById('speechBox');
    const logBox = document.getElementById('logBox');
    
    let isListening = false;
    let websocket = null;
    
    // WebSocket connection
    function connectWebSocket() {
        const wsUrl = `ws://${window.location.hostname}:8081`;
        
        try {
            websocket = new WebSocket(wsUrl);
            
            websocket.onopen = function(event) {
                console.log('Connected to Dados WebSocket');
                addSystemMessage('Connected to voice agent');
            };
            
            websocket.onmessage = function(event) {
                const message = JSON.parse(event.data);
                handleWebSocketMessage(message);
            };
            
            websocket.onclose = function(event) {
                console.log('WebSocket connection closed');
                addSystemMessage('Disconnected from voice agent');
                // Attempt to reconnect after 3 seconds
                setTimeout(connectWebSocket, 3000);
            };
            
            websocket.onerror = function(error) {
                console.error('WebSocket error:', error);
                addSystemMessage('Connection error - retrying...');
            };
            
        } catch (error) {
            console.error('Failed to connect to WebSocket:', error);
            addSystemMessage('Failed to connect to voice agent');
            setTimeout(connectWebSocket, 3000);
        }
    }
    
    function handleWebSocketMessage(message) {
        switch (message.type) {
            case 'init':
                // Load initial data
                message.data.speech_history.reverse().forEach(addSpeechEntry);
                message.data.action_history.reverse().forEach(addActionEntry);
                break;
            case 'speech':
                addSpeechEntry(message.data);
                break;
            case 'action':
                addActionEntry(message.data);
                break;
        }
    }
    
    function addSpeechEntry(entry) {
        const entryDiv = document.createElement('div');
        entryDiv.className = 'speech-entry';
        entryDiv.innerHTML = `
            <span class="timestamp">${entry.timestamp}</span>
            <span class="text">"${entry.text}"</span>
        `;
        speechBox.insertBefore(entryDiv, speechBox.firstChild);
        
        // Keep only last 20 entries
        while (speechBox.children.length > 20) {
            speechBox.removeChild(speechBox.lastChild);
        }
    }
    
    function addActionEntry(entry) {
        const entryDiv = document.createElement('div');
        entryDiv.className = `log-entry ${entry.success ? 'success' : 'info'}`;
        entryDiv.innerHTML = `
            <span class="timestamp">${entry.timestamp}</span>
            <span class="action">${entry.action}</span>
            <span class="details">${entry.details}</span>
        `;
        logBox.insertBefore(entryDiv, logBox.firstChild);
        
        // Keep only last 20 entries
        while (logBox.children.length > 20) {
            logBox.removeChild(logBox.lastChild);
        }
    }
    
    function addSystemMessage(message) {
        const timestamp = new Date().toLocaleTimeString('en-US', { 
            hour12: false, 
            hour: '2-digit', 
            minute: '2-digit', 
            second: '2-digit' 
        });
        
        addActionEntry({
            timestamp: `[${timestamp}]`,
            action: 'System',
            details: message,
            success: false
        });
    }
    
    // Handle start button click - trigger audio recording
    startBtn.addEventListener('click', function() {
        isListening = !isListening;
        
        if (isListening) {
            startBtn.classList.add('pulsing');
            addSystemMessage('Recording started - speak now...');
            startRecording();
        } else {
            startBtn.classList.remove('pulsing');
            addSystemMessage('Recording stopped');
            stopRecording();
        }
    });
    
    let mediaRecorder = null;
    let audioChunks = [];
    
    async function startRecording() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorder = new MediaRecorder(stream);
            audioChunks = [];
            
            mediaRecorder.ondataavailable = function(event) {
                audioChunks.push(event.data);
            };
            
            mediaRecorder.onstop = function() {
                const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                // Send audio to backend for processing
                sendAudioToBackend(audioBlob);
                
                // Stop all tracks to release microphone
                stream.getTracks().forEach(track => track.stop());
            };
            
            mediaRecorder.start();
        } catch (error) {
            console.error('Error accessing microphone:', error);
            addSystemMessage('Microphone access denied. Use RIGHT OPTION key instead.');
            isListening = false;
            startBtn.classList.remove('pulsing');
        }
    }
    
    function stopRecording() {
        if (mediaRecorder && mediaRecorder.state === 'recording') {
            mediaRecorder.stop();
        }
    }
    
    function sendAudioToBackend(audioBlob) {
        // For now, just show a message that audio was captured
        // In a full implementation, this would send the audio to the backend
        addSystemMessage(`Audio captured (${Math.round(audioBlob.size / 1024)}KB) - processing...`);
        
        // Simulate processing delay
        setTimeout(() => {
            addSystemMessage('Note: Use RIGHT OPTION key for actual voice control');
        }, 1000);
    }
    
    // Connect to WebSocket on page load
    connectWebSocket();
});
