document.addEventListener('DOMContentLoaded', function() {
    const chatMessages = document.getElementById('chatMessages');
    const userInput = document.getElementById('userInput');
    const sendButton = document.getElementById('sendButton');
    const recordButton = document.getElementById('recordButton');
    const recordingStatus = document.getElementById('recordingStatus');
    
    let mediaRecorder;
    let audioChunks = [];
    let isRecording = false;
    
    // Function to add a user message to the chat
    function addUserMessage(originalText, translatedText) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message user-message';
        
        // Add original text
        messageDiv.textContent = originalText;
        
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
    
    // Function to add a bot message to the chat
    function addBotMessage(originalText, translatedText, audioId) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message bot-message';
        
        // Add original text
        messageDiv.textContent = originalText;
        
        // Add response sections
        const responseSection = document.createElement('div');
        responseSection.className = 'response-section';
        
        // Add translation if available
        if (translatedText) {
            const translationSpan = document.createElement('span');
            translationSpan.innerHTML = `<span class="response-label">English:</span> ${translatedText}`;
            responseSection.appendChild(translationSpan);
        }
        
        // Add play button for audio if available
        if (audioId) {
            const playButton = document.createElement('button');
            playButton.className = 'play-audio';
            playButton.innerHTML = '🔊 Play';
            playButton.dataset.audioId = audioId;
            playButton.addEventListener('click', function() {
                playAudio(audioId);
            });
            responseSection.appendChild(playButton);
        }
        
        messageDiv.appendChild(responseSection);
        chatMessages.appendChild(messageDiv);
        scrollToBottom();
    }
    
    // Function to scroll to the bottom of the chat
    function scrollToBottom() {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
    
    // Function to play audio
    function playAudio(audioId) {
        fetch(`/api/audio/${audioId}`)
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
            })
            .catch(error => {
                console.error('Error playing audio:', error);
                alert('Error playing audio. Please try again.');
            });
    }
    
    // Function to send text message
    async function sendTextMessage() {
        const message = userInput.value.trim();
        if (message === '') return;
        
        // Clear input field
        userInput.value = '';
        
        // Show loading state
        recordingStatus.textContent = "处理中...";
        
        try {
            // Get language from the page URL
            const language = window.location.pathname.includes('chinese') ? 'chinese' : 'japanese';
            
            // Send message to backend and get response
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
            
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            
            const data = await response.json();
            
            // Add user message to chat
            addUserMessage(message, data.translatedUserText);
            
            // Add bot response to chat
            addBotMessage(data.botResponse, data.botResponseEnglish, data.audioId);
            
            // Reset status
            recordingStatus.textContent = "准备就绪";
            
        } catch (error) {
            console.error('Error:', error);
            recordingStatus.textContent = "发生错误，请重试";
        }
    }
    
    // Function to handle voice recording
    async function toggleRecording() {
        const sampleRate = 44100;
        const numChannels = 1;
        const bitsPerSample = 16;
        
        if (!isRecording) {
            // Start recording
            audioChunks = [];
            
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: { sampleRate, channelCount: numChannels } });
                
                // Explicitly specify audio/webm MIME type for broad compatibility
                mediaRecorder = new MediaRecorder(stream);
                
                mediaRecorder.ondataavailable = (event) => {
                    audioChunks.push(event.data);
                };
                
                mediaRecorder.onstop = async () => {
                    // Create audio blob - explicitly use webm format
                    const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                    
                    // Show loading state
                    recordingStatus.textContent = "处理中...";
                    
                    // Create form data
                    const formData = new FormData();
                    formData.append('audio', audioBlob, 'recording.wav');  // Explicitly name the file with .webm extension
                    formData.append('language', window.location.pathname.includes('chinese') ? 'chinese' : 'japanese');
                    
                    try {
                        // Send audio to backend
                        const response = await fetch('/api/voice-chat', {
                            method: 'POST',
                            body: formData
                        });
                        
                        if (!response.ok) {
                            throw new Error('Network response was not ok');
                        }
                        
                        const data = await response.json();
                        
                        // Add user message to chat
                        addUserMessage(data.transcribedText, data.translatedUserText);
                        
                        // Add bot response to chat
                        addBotMessage(data.botResponse, data.botResponseEnglish, data.audioId);
                        
                        // Reset status
                        recordingStatus.textContent = "准备就绪";
                        
                    } catch (error) {
                        console.error('Error:', error);
                        recordingStatus.textContent = "发生错误，请重试";
                    }
                };
                
                mediaRecorder.start();
                isRecording = true;
                
                // Update UI
                recordButton.classList.add('recording');
                recordButton.querySelector('.button-text').textContent = "点击停止录音";
                recordingStatus.textContent = "正在录音...";
                
            } catch (error) {
                console.error('Error accessing microphone:', error);
                alert('无法访问麦克风。请确保您已授予麦克风权限。');
            }
            
        } else {
            // Stop recording
            mediaRecorder.stop();
            isRecording = false;
            
            // Stop all tracks in the stream
            mediaRecorder.stream.getTracks().forEach(track => track.stop());
            
            // Update UI
            recordButton.classList.remove('recording');
            recordButton.querySelector('.button-text').textContent = "按下开始录音";
            recordingStatus.textContent = "正在处理...";
        }
    }
    
    // Event listener for record button
    recordButton.addEventListener('click', toggleRecording);
    
    // Event listener for send button
    sendButton.addEventListener('click', sendTextMessage);
    
    // Event listener for Enter key in text input
    userInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            sendTextMessage();
        }
    });
});