document.addEventListener('DOMContentLoaded', function() {
    const chatMessages = document.getElementById('chatMessages');
    const userInput = document.getElementById('userInput');
    const sendButton = document.getElementById('sendButton');
    const recordButton = document.getElementById('recordButton');
    const recordingStatus = document.getElementById('recordingStatus');
    
    let mediaRecorder;
    let audioChunks = [];
    let isRecording = false;

    // --- 1. Global Audio Player (The Fix) ---
    // We use a single global audio object. We "bless" (load) this object
    // immediately whenever the user clicks a button.
    const globalAudioPlayer = new Audio();

    // --- 2. UI Helper Functions ---

    function scrollToBottom() {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function playAudio(audioId) {
        const audioUrl = `/api/audio/${audioId}`;
        
        // Reset the player
        globalAudioPlayer.pause();
        globalAudioPlayer.currentTime = 0;
        globalAudioPlayer.src = audioUrl;
        
        // Attempt to play with a retry mechanism (in case file system is slow)
        const attemptPlay = (retries = 3) => {
            globalAudioPlayer.play().catch(error => {
                if (error.name === 'NotAllowedError') {
                    console.error("Autoplay blocked. Browser lost user gesture context.");
                    recordingStatus.textContent = "⚠️ Click 'Play' in chat (Autoplay blocked)";
                } else if (retries > 0) {
                    // Retry if file not ready (404)
                    setTimeout(() => attemptPlay(retries - 1), 500);
                } else {
                    console.error('Audio playback error:', error);
                }
            });
        };
        
        attemptPlay();
    }

    function addUserMessage(originalText, translatedText) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message user-message';
        
        // Add original text
        const textDiv = document.createElement('div');
        textDiv.textContent = originalText;
        messageDiv.appendChild(textDiv);
        
        // Add translation if available
        if (translatedText) {
            const translationDiv = document.createElement('div');
            translationDiv.className = 'translation';
            translationDiv.textContent = translatedText;
            messageDiv.appendChild(translationDiv);
        }
        
        chatMessages.appendChild(messageDiv);
        scrollToBottom();
    }

    function addBotMessage(originalText, translatedText, audioId) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message bot-message';
        
        // Add original text
        const textDiv = document.createElement('div');
        textDiv.textContent = originalText;
        messageDiv.appendChild(textDiv);
        
        // Add response sections
        const responseSection = document.createElement('div');
        responseSection.className = 'response-section';
        
        // Add translation if available
        if (translatedText) {
            const translationSpan = document.createElement('div');
            translationSpan.className = 'translation';
            translationSpan.innerHTML = `<span class="response-label">En:</span> ${translatedText}`;
            responseSection.appendChild(translationSpan);
        }
        
        // Add play button for audio if available
        if (audioId) {
            const playButton = document.createElement('button');
            playButton.className = 'play-audio';
            playButton.innerHTML = '🔊 Play';
            // This click will always work because it is a direct user action
            playButton.onclick = function() { playAudio(audioId); };
            responseSection.appendChild(playButton);
        }
        
        messageDiv.appendChild(responseSection);
        chatMessages.appendChild(messageDiv);
        scrollToBottom();
    }

    // --- 3. Text Chat Logic ---

    async function sendTextMessage() {
        const message = userInput.value.trim();
        if (message === '') return;
        
        // 1. BLESS THE AUDIO: User clicked send, so we prep the player immediately
        globalAudioPlayer.src = '';
        globalAudioPlayer.load();
        
        userInput.value = '';
        recordingStatus.textContent = "Thinking...";
        
        try {
            const language = window.location.pathname.includes('chinese') ? 'chinese' : 'japanese';
            
            const response = await fetch('/api/text-chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    message: message,
                    language: language
                })
            });
            
            if (!response.ok) throw new Error('Network response was not ok');
            
            const data = await response.json();
            
            addUserMessage(message, data.translatedUserText);
            addBotMessage(data.botResponse, data.botResponseEnglish, data.audioId);
            
            if (data.audioId) {
                playAudio(data.audioId);
            }
            
            recordingStatus.textContent = "Ready";
            
        } catch (error) {
            console.error('Error:', error);
            recordingStatus.textContent = "Error, please try again";
        }
    }

    // --- 4. Voice Recording Logic ---

    async function toggleRecording() {
        const sampleRate = 44100;
        const numChannels = 1;
        
        if (!isRecording) {
            // --- START RECORDING ---
            audioChunks = [];
            
            try {
                // HTTPS check
                if (location.protocol !== 'https:' && location.hostname !== 'localhost') {
                    alert('HTTPS is required for microphone access.');
                    return;
                }
                
                const stream = await navigator.mediaDevices.getUserMedia({ 
                    audio: { 
                        sampleRate: sampleRate,
                        channelCount: numChannels,
                        echoCancellation: true,
                        noiseSuppression: true
                    } 
                });
                
                // Browser compatibility check
                let mimeType = 'audio/webm';
                if (MediaRecorder.isTypeSupported('audio/mp4')) {
                    mimeType = 'audio/mp4'; // Safari
                } else if (!MediaRecorder.isTypeSupported('audio/webm')) {
                    mimeType = ''; // Default
                }
                
                mediaRecorder = new MediaRecorder(stream, 
                    mimeType ? { mimeType, audioBitsPerSecond: 128000 } : {}
                );
                
                mediaRecorder.ondataavailable = (event) => {
                    if (event.data.size > 0) {
                        audioChunks.push(event.data);
                    }
                };
                
                mediaRecorder.onstop = async () => {
                    recordingStatus.textContent = "Processing...";
                    
                    const audioBlob = new Blob(audioChunks, { type: mimeType || 'audio/webm' });
                    
                    try {
                        // Convert to WAV (Keep existing logic for compatibility)
                        const wavBlob = await convertToWav(audioBlob, sampleRate, numChannels);
                        
                        const formData = new FormData();
                        formData.append('audio', wavBlob, 'recording.wav');
                        formData.append('language', window.location.pathname.includes('chinese') ? 'chinese' : 'japanese');
                        
                        const response = await fetch('/api/voice-chat', {
                            method: 'POST',
                            body: formData
                        });
                        
                        if (!response.ok) throw new Error('Server error: ' + response.status);
                        
                        const data = await response.json();
                        
                        addUserMessage(data.transcribedText, data.translatedUserText);
                        addBotMessage(data.botResponse, data.botResponseEnglish, data.audioId);
                        
                        if (data.audioId) {
                            playAudio(data.audioId);
                        }
                        
                        recordingStatus.textContent = "Ready";
                        
                    } catch (error) {
                        console.error('Processing error:', error);
                        recordingStatus.textContent = "Processing failed";
                    }
                };
                
                mediaRecorder.onerror = (event) => {
                    console.error('MediaRecorder error:', event.error);
                    recordingStatus.textContent = "Recording Error";
                    isRecording = false;
                    recordButton.classList.remove('recording');
                    recordButton.querySelector('.button-text').textContent = "Start Recording";
                };
                
                mediaRecorder.start(1000);
                isRecording = true;
                
                recordButton.classList.add('recording');
                recordButton.querySelector('.button-text').textContent = "Stop Recording";
                recordingStatus.textContent = "Recording...";
                
            } catch (error) {
                console.error('Microphone access error:', error);
                alert("Microphone access denied or not found.");
                recordingStatus.textContent = "Ready";
            }
            
        } else {
            // --- STOP RECORDING ---
            
            // 1. BLESS THE AUDIO: This is the critical fix for Voice.
            // The user just clicked "Stop", so we use this gesture to unlock audio.
            globalAudioPlayer.src = '';
            globalAudioPlayer.load();

            if (mediaRecorder && mediaRecorder.state !== 'inactive') {
                mediaRecorder.stop();
                isRecording = false;
                
                // Stop tracks
                mediaRecorder.stream.getTracks().forEach(track => track.stop());
                
                recordButton.classList.remove('recording');
                recordButton.querySelector('.button-text').textContent = "Start Recording";
                recordingStatus.textContent = "Processing...";
            }
        }
    }

    // --- 5. WAV Conversion Helpers (Unchanged) ---

    async function convertToWav(audioBlob, sampleRate, numChannels) {
        try {
            const AudioContextClass = window.AudioContext || window.webkitAudioContext;
            const audioContext = new AudioContextClass({ sampleRate });
            const arrayBuffer = await audioBlob.arrayBuffer();
            const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);
            const wavBuffer = createWavFile(audioBuffer, numChannels);
            audioContext.close();
            return new Blob([wavBuffer], { type: 'audio/wav' });
        } catch (error) {
            console.error('WAV conversion error:', error);
            throw new Error('Audio conversion failed');
        }
    }

    function createWavFile(audioBuffer, numChannels) {
        const length = audioBuffer.length;
        const sampleRate = audioBuffer.sampleRate;
        const bitsPerSample = 16;
        const bytesPerSample = bitsPerSample / 8;
        const blockAlign = numChannels * bytesPerSample;
        const byteRate = sampleRate * blockAlign;
        const dataSize = length * blockAlign;
        
        const buffer = new ArrayBuffer(44 + dataSize);
        const view = new DataView(buffer);
        
        writeString(view, 0, 'RIFF');
        view.setUint32(4, 36 + dataSize, true);
        writeString(view, 8, 'WAVE');
        writeString(view, 12, 'fmt ');
        view.setUint32(16, 16, true); 
        view.setUint16(20, 1, true); 
        view.setUint16(22, numChannels, true);
        view.setUint32(24, sampleRate, true);
        view.setUint32(28, byteRate, true);
        view.setUint16(32, blockAlign, true);
        view.setUint16(34, bitsPerSample, true);
        writeString(view, 36, 'data');
        view.setUint32(40, dataSize, true);
        
        const floatData = audioBuffer.getChannelData(0);
        let offset = 44;
        
        for (let i = 0; i < length; i++) {
            const sample = Math.max(-1, Math.min(1, floatData[i]));
            const pcm = sample < 0 ? sample * 32768 : sample * 32767;
            view.setInt16(offset, pcm, true);
            offset += bytesPerSample;
        }
        
        return buffer;
    }

    function writeString(view, offset, string) {
        for (let i = 0; i < string.length; i++) {
            view.setUint8(offset + i, string.charCodeAt(i));
        }
    }

    // --- 6. Event Listeners ---

    if (recordButton) {
        recordButton.addEventListener('click', toggleRecording);
    } else {
        console.error("Record button not found in DOM");
    }

    if (sendButton) {
        sendButton.addEventListener('click', sendTextMessage);
    }

    if (userInput) {
        userInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                sendTextMessage();
            }
        });
    }
});