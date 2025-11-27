const sessionId = crypto.randomUUID();

// Automatically detect language from page
let language = "chinese"; // default fallback

// Try to detect language from multiple sources
function detectLanguage() {
    // Method 1: Check for data attribute on body
    const body = document.body;
    if (body.dataset.language) {
        return body.dataset.language;
    }
    
    // Method 2: Check for language in container div
    const container = document.querySelector('.chat-container');
    if (container && container.dataset.language) {
        return container.dataset.language;
    }
    
    // Method 3: Check HTML lang attribute
    const htmlLang = document.documentElement.lang;
    if (htmlLang) {
        if (htmlLang.startsWith('zh')) return 'chinese';
        if (htmlLang.startsWith('ja')) return 'japanese';
    }
    
    // Method 4: Check HTML data-chat-language attribute
    const chatLang = document.documentElement.dataset.chatLanguage;
    if (chatLang) return chatLang;
    
    // Method 5: Check page title or header for language indicators
    const title = document.title.toLowerCase();
    if (title.includes('chinese') || title.includes('中文')) return 'chinese';
    if (title.includes('japanese') || title.includes('日本語')) return 'japanese';
    
    // Method 6: Check for language-specific class on chat-header
    const chatHeader = document.querySelector('.chat-header');
    if (chatHeader) {
        if (chatHeader.classList.contains('chinese')) return 'chinese';
        if (chatHeader.classList.contains('japanese')) return 'japanese';
    }
    
    // Default fallback
    return 'chinese';
}

language = detectLanguage();
console.log(`Detected language: ${language}`);

// Language-specific text configurations
const languageConfig = {
    chinese: {
        recording: '正在录音...',
        processing: '处理中...',
        thinking: '思考中...',
        ready: '准备就绪',
        stop: '停止',
        startRecording: '按下开始录音',
        audioReady: '音频已准备好（点击任意按钮启用）',
        error: '抱歉，出现错误。请重试。',
        micError: '无法访问麦克风',
        you: '您',
        assistant: '助手',
        system: '系统'
    },
    japanese: {
        recording: '録音中...',
        processing: '処理中...',
        thinking: '考え中...',
        ready: '準備完了',
        stop: '停止',
        startRecording: '録音を開始',
        audioReady: 'オーディオ準備完了（ボタンをクリックして有効化）',
        error: '申し訳ございません。エラーが発生しました。もう一度お試しください。',
        micError: 'マイクにアクセスできません',
        you: 'あなた',
        assistant: 'アシスタント',
        system: 'システム'
    }
};

// Get current language text
const getText = (key) => languageConfig[language][key] || languageConfig.chinese[key];

// DOM Elements
const recordButton = document.getElementById('recordButton');
const recordingStatus = document.getElementById('recordingStatus');
const chatMessages = document.getElementById('chatMessages');
const userInput = document.getElementById('userInput');
const sendButton = document.getElementById('sendButton');

// Get or create audio player with proper settings for iOS/Safari
let audioPlayer = document.getElementById('audioPlayer');
if (!audioPlayer) {
    audioPlayer = document.createElement('audio');
    audioPlayer.id = 'audioPlayer';
    document.body.appendChild(audioPlayer);
}

// Ensure audio player has correct attributes
audioPlayer.preload = 'none';
audioPlayer.setAttribute('playsinline', ''); // Critical for iOS
audioPlayer.style.display = 'none';

// Track if user has interacted (required for iOS autoplay)
let userHasInteracted = false;

// Audio context for iOS (helps with autoplay restrictions)
let audioContext = null;
function initAudioContext() {
    if (!audioContext && typeof AudioContext !== 'undefined') {
        audioContext = new AudioContext();
    }
    return audioContext;
}

let mediaRecorder;
let audioChunks = [];
let isRecording = false;

// Mark user interaction on any button click
document.addEventListener('click', () => {
    if (!userHasInteracted) {
        userHasInteracted = true;
        console.log('User interaction detected - audio playback enabled');
        
        // Resume audio context if suspended (iOS requirement)
        const ctx = initAudioContext();
        if (ctx && ctx.state === 'suspended') {
            ctx.resume();
        }
    }
}, { once: true });

// Audio Recording Logic
recordButton.addEventListener('click', async () => {
    if (!isRecording) {
        await startRecording();
    } else {
        stopRecording();
    }
});

async function startRecording() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ 
            audio: {
                echoCancellation: true,
                noiseSuppression: true,
                sampleRate: 44100
            }
        });
        
        mediaRecorder = new MediaRecorder(stream, {
            mimeType: MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : 'audio/mp4'
        });
        audioChunks = [];

        mediaRecorder.ondataavailable = event => {
            if (event.data.size > 0) {
                audioChunks.push(event.data);
            }
        };
        
        mediaRecorder.onstop = sendAudio;
        
        mediaRecorder.onerror = (event) => {
            console.error('MediaRecorder error:', event.error);
            alert(getText('error'));
            resetRecordingState();
        };

        mediaRecorder.start();
        isRecording = true;
        recordButton.classList.add('recording');
        recordButton.querySelector('.button-text').textContent = getText('stop');
        recordingStatus.textContent = getText('recording');
    } catch (err) {
        alert(getText('micError'));
        console.error('Microphone error:', err);
        resetRecordingState();
    }
}

function stopRecording() {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
        mediaRecorder.stop();
        mediaRecorder.stream.getTracks().forEach(track => track.stop());
    }
    isRecording = false;
    recordButton.classList.remove('recording');
    recordButton.querySelector('.button-text').textContent = getText('startRecording');
    recordingStatus.textContent = getText('processing');
}

function resetRecordingState() {
    isRecording = false;
    recordButton.classList.remove('recording');
    recordButton.querySelector('.button-text').textContent = getText('startRecording');
    recordingStatus.textContent = getText('ready');
}

// Sending Logic
async function sendAudio() {
    if (audioChunks.length === 0) {
        console.error('No audio data recorded');
        alert(getText('error'));
        resetRecordingState();
        return;
    }

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

    // Add user message to UI immediately
    addMessage(getText('you'), text, null, true, null, null);
    userInput.value = '';

    const formData = new FormData();
    formData.append('text', text);
    formData.append('language', language);
    formData.append('session_id', sessionId);

    await processResponse(formData);
}

async function processResponse(formData) {
    try {
        recordingStatus.textContent = getText('thinking');
        
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
            addMessage(getText('you'), data.transcribedText, null, true, data.messageId, 'user_english');
        }

        // Handle bot response
        if (data.botResponse) {
            addMessage(getText('assistant'), data.botResponse, null, false, data.messageId, 'bot_english');
        }

        // Play audio if available - with robust error handling
        if (data.audioId) {
            await playAudioWithFallback(data.audioId);
        }
        
    } catch (e) {
        console.error('Chat error:', e);
        addMessage(getText('system'), getText('error'), null, false, null, null);
    } finally {
        recordingStatus.textContent = getText('ready');
    }
}

// Improved audio playback with fallback strategies
async function playAudioWithFallback(audioId) {
    const audioUrl = `/api/audio/${audioId}`;
    
    try {
        // Strategy 1: Standard audio element play
        audioPlayer.src = audioUrl;
        
        // Load the audio first
        await new Promise((resolve, reject) => {
            audioPlayer.onloadeddata = resolve;
            audioPlayer.onerror = reject;
            audioPlayer.load();
        });
        
        // Attempt to play
        const playPromise = audioPlayer.play();
        
        if (playPromise !== undefined) {
            await playPromise;
            console.log('Audio playback started successfully');
        }
    } catch (err) {
        console.error('Audio playback error:', err);
        
        // Strategy 2: Try resuming audio context and retrying (iOS fix)
        if (err.name === 'NotAllowedError' || err.name === 'NotSupportedError') {
            const ctx = initAudioContext();
            if (ctx && ctx.state === 'suspended') {
                try {
                    await ctx.resume();
                    await audioPlayer.play();
                    console.log('Audio playback started after context resume');
                    return;
                } catch (retryErr) {
                    console.error('Retry after context resume failed:', retryErr);
                }
            }
        }
        
        // Strategy 3: Create new audio element (Safari sometimes needs this)
        try {
            const newAudio = new Audio(audioUrl);
            newAudio.preload = 'auto';
            newAudio.setAttribute('playsinline', '');
            await newAudio.play();
            console.log('Audio playback started with new element');
        } catch (finalErr) {
            console.error('All audio playback strategies failed:', finalErr);
            // Don't show error to user - audio failure is not critical
        }
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
                transDiv.style.color = '#999';
                
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

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
        mediaRecorder.stop();
        mediaRecorder.stream.getTracks().forEach(track => track.stop());
    }
    if (audioContext) {
        audioContext.close();
    }
});