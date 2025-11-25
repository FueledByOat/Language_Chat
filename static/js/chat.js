const sessionId = crypto.randomUUID();

// Automatically detect language from page
let language = "chinese"; // default fallback

// Try to detect language from multiple sources
function detectLanguage() {
    // Method 1: Check for data attribute on body or container
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
    
    // Method 4: Check page title or header for language indicators
    const title = document.title.toLowerCase();
    if (title.includes('chinese') || title.includes('中文')) return 'chinese';
    if (title.includes('japanese') || title.includes('日本語')) return 'japanese';
    
    // Method 5: Check for language-specific class on chat-header
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

// Create audio player with iOS/Safari-compatible settings
let audioPlayer = document.getElementById('audioPlayer');
if (!audioPlayer) {
    audioPlayer = document.createElement('audio');
    audioPlayer.id = 'audioPlayer';
    audioPlayer.style.display = 'none';
    document.body.appendChild(audioPlayer);
}

let mediaRecorder;
let audioChunks = [];
let isRecording = false;

// Audio Recording Logic
recordButton.addEventListener('click', async () => {
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
        recordButton.querySelector('.button-text').textContent = getText('stop');
        recordingStatus.textContent = getText('recording');
    } catch (err) {
        alert(getText('micError'));
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
    recordButton.querySelector('.button-text').textContent = getText('startRecording');
    recordingStatus.textContent = getText('processing');
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

        // Play audio if available - SIMPLE APPROACH (matches scenario pages)
        if (data.audioId) {
            audioPlayer.src = `/api/audio/${data.audioId}`;
            audioPlayer.play().catch(err => console.error('Audio play error:', err));
        }
        
    } catch (e) {
        console.error('Chat error:', e);
        addMessage(getText('system'), getText('error'), null, false, null, null);
    } finally {
        recordingStatus.textContent = getText('ready');
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