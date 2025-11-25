const sessionId = crypto.randomUUID();
const language = "chinese";

// DOM Elements
const recordButton = document.getElementById('recordButton');
const recordingStatus = document.getElementById('recordingStatus');
const chatMessages = document.getElementById('chatMessages');
const userInput = document.getElementById('userInput');
const sendButton = document.getElementById('sendButton');

// Create audio player with iOS/Safari-compatible settings
let audioPlayer = document.getElementById('audioPlayer');
if (!audioPlayer) {
    audioPlayer = document.createElement('audio');
    audioPlayer.id = 'audioPlayer';
    audioPlayer.style.display = 'none';
    audioPlayer.preload = 'auto';
    audioPlayer.playsInline = true; // CRITICAL for iOS
    document.body.appendChild(audioPlayer);
}

let mediaRecorder;
let audioChunks = [];
let isRecording = false;
let audioInitialized = false;

// Initialize audio on first user interaction (required for iOS/Safari)
async function initializeAudio() {
    if (!audioInitialized) {
        try {
            // Play silent audio to unlock audio playback on iOS
            const silentAudio = 'data:audio/mp3;base64,SUQzBAAAAAAAI1RTU0UAAAAPAAADTGF2ZjU4Ljc2LjEwMAAAAAAAAAAAAAAA//tQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAASW5mbwAAAA8AAAACAAABhADAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1f////////////////////////////////8AAAAATGF2YzU4LjEzAAAAAAAAAAAAAAAAJAAAAAAAAAAAYYSAAAAAAAD/+xDEAAADSAZQAMYQnCu/ioB4AgwACAIAkAgQJH//////////8+r//////////+r/////////4gMEAMMw4EBAMEwwGBA2GQwIBgUDhMKCA4PDI0Pgg8Qjw8NCwoDAwKCA4HAwKCQgKCAoIAwMAQABgEAgEBA//sQxAoAAxkGUADGEJ4rv///f/////+v/////////v//////////8EAQBAwGBwKBAMCAYDAgEBAECAICBAMDAQEAQBAICAQDAgEBAH/+xDEFAAC+QpSAMYQrCu////////+v/////////v//////////4QBAEAwKBAQBgMCAYEAgEBAMCAYFAYEAwGBAMCAQDAgEBAE//7EMQZAITCC6AAZiAAADSAAAAAEQBAH//////////////////////////////////////////';
            
            audioPlayer.src = silentAudio;
            audioPlayer.volume = 0;
            await audioPlayer.play();
            audioPlayer.pause();
            audioPlayer.volume = 1;
            audioInitialized = true;
            console.log('Audio initialized successfully');
        } catch (err) {
            console.log('Audio initialization deferred:', err);
            // Don't throw - user can still try to use the app
        }
    }
}

// Audio Recording Logic
recordButton.addEventListener('click', async () => {
    // Initialize audio on first click
    await initializeAudio();
    
    if (!isRecording) {
        startRecording();
    } else {
        stopRecording();
    }
});

async function startRecording() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];

        mediaRecorder.ondataavailable = event => audioChunks.push(event.data);
        mediaRecorder.onstop = sendAudio;

        mediaRecorder.start();
        isRecording = true;
        recordButton.classList.add('recording');
        recordButton.querySelector('.button-text').textContent = '停止';
        recordingStatus.textContent = '正在录音...';
    } catch (err) {
        alert('无法访问麦克风');
        console.error('Microphone error:', err);
    }
}

function stopRecording() {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
        mediaRecorder.stop();
        mediaRecorder.stream.getTracks().forEach(track => track.stop());
    }
    isRecording = false;
    recordButton.classList.remove('recording');
    recordButton.querySelector('.button-text').textContent = '按下开始录音';
    recordingStatus.textContent = '处理中...';
}

// Sending Logic
async function sendAudio() {
    const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
    const formData = new FormData();
    formData.append('audio', audioBlob, 'input.wav');
    formData.append('language', language);
    formData.append('session_id', sessionId);
    
    await processResponse(formData);
}

async function sendText() {
    const text = userInput.value.trim();
    if (!text) return;

    // Initialize audio on first send (in case user types before clicking record)
    await initializeAudio();

    // Add user message to UI immediately
    addMessage('您', text, null, true, null, null);
    userInput.value = '';

    const formData = new FormData();
    formData.append('text', text);
    formData.append('language', language);
    formData.append('session_id', sessionId);

    await processResponse(formData);
}

async function processResponse(formData) {
    try {
        recordingStatus.textContent = '思考中...';
        
        const response = await fetch('/api/chat', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            throw new Error(`Server error: ${response.status}`);
        }
        
        const data = await response.json();

        // Handle transcribed text (from audio input)
        if (data.transcribedText) {
            addMessage('您', data.transcribedText, null, true, data.messageId, 'user_english');
        }

        // Handle bot response
        if (data.botResponse) {
            addMessage('助手', data.botResponse, null, false, data.messageId, 'bot_english');
        }

        // Play audio if available - FIXED FOR SAFARI/iOS
        if (data.audioId) {
            try {
                // Set the source
                audioPlayer.src = `/api/audio/${data.audioId}`;
                
                // Explicitly load the audio
                audioPlayer.load();
                
                // Small delay to ensure load starts (helps on slower connections)
                await new Promise(resolve => setTimeout(resolve, 100));
                
                // Attempt to play
                const playPromise = audioPlayer.play();
                
                if (playPromise !== undefined) {
                    await playPromise;
                    console.log('Audio playing successfully');
                }
            } catch (err) {
                console.error('Audio play error:', err);
                
                // Show user-friendly message for autoplay restrictions
                if (err.name === 'NotAllowedError' || err.name === 'NotSupportedError') {
                    recordingStatus.textContent = '音频已准备好（点击任意按钮启用）';
                    
                    // Try to play again on next user interaction
                    const retryPlay = async () => {
                        try {
                            await audioPlayer.play();
                            document.removeEventListener('click', retryPlay);
                            document.removeEventListener('touchstart', retryPlay);
                        } catch (e) {
                            console.log('Retry play failed:', e);
                        }
                    };
                    
                    // Add listeners for next interaction
                    document.addEventListener('click', retryPlay, { once: true });
                    document.addEventListener('touchstart', retryPlay, { once: true });
                }
            }
        }
        
    } catch (e) {
        console.error('Chat error:', e);
        addMessage('系统', '抱歉，出现错误。请重试。', null, false, null, null);
    } finally {
        recordingStatus.textContent = '准备就绪';
    }
}

// Add message with spoiler translation support
function addMessage(role, text, initialTranslation, isUser, messageId, jsonKey) {
    const messageBubble = document.createElement('div');
    messageBubble.className = `message ${isUser ? 'user-message' : 'bot-message'}`;

    // Main message text
    const textDiv = document.createElement('div');
    textDiv.className = 'message-text';
    textDiv.textContent = text;
    messageBubble.appendChild(textDiv);

    // Only add translation spoiler if we have a messageId
    if (messageId && jsonKey) {
        const transDiv = document.createElement('div');
        transDiv.className = 'spoiler-hidden';
        transDiv.textContent = initialTranslation || 'Click to reveal translation';
        
        transDiv.onclick = async () => {
            // Already visible? Do nothing
            if (transDiv.classList.contains('spoiler-visible')) return;

            // Fetch translation if not already loaded
            if (!initialTranslation) {
                transDiv.textContent = 'Loading...';
                transDiv.style.color = '#999'; // Make "Loading..." visible
                
                try {
                    const translation = await fetchTranslationWithRetry(messageId, jsonKey);
                    transDiv.textContent = translation;
                    initialTranslation = translation;
                } catch (err) {
                    console.error('Translation error:', err);
                    transDiv.textContent = 'Translation unavailable';
                    transDiv.classList.remove('spoiler-hidden');
                    transDiv.classList.add('spoiler-visible');
                    return;
                }
            }

            // Reveal translation
            transDiv.classList.remove('spoiler-hidden');
            transDiv.classList.add('spoiler-visible');
        };

        messageBubble.appendChild(transDiv);
    }

    chatMessages.appendChild(messageBubble);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Fetch translation with retry logic
async function fetchTranslationWithRetry(messageId, key, attempts = 0) {
    const maxAttempts = 6;
    
    if (attempts >= maxAttempts) {
        throw new Error('Translation timeout');
    }

    try {
        const res = await fetch(`/api/translation/${messageId}`);
        
        if (res.status === 202) {
            // Still pending, wait and retry
            await new Promise(resolve => setTimeout(resolve, 1000));
            return fetchTranslationWithRetry(messageId, key, attempts + 1);
        }
        
        if (!res.ok) {
            throw new Error(`HTTP ${res.status}`);
        }
        
        const data = await res.json();
        return data[key] || 'Translation not found';
        
    } catch (err) {
        console.error(`Translation fetch attempt ${attempts + 1} failed:`, err);
        
        if (attempts < maxAttempts - 1) {
            await new Promise(resolve => setTimeout(resolve, 1000));
            return fetchTranslationWithRetry(messageId, key, attempts + 1);
        }
        
        throw err;
    }
}

// Event Listeners for Text Input
sendButton.addEventListener('click', sendText);
userInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        sendText();
    }
});