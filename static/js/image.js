document.addEventListener('DOMContentLoaded', function () {
    const recordButton = document.getElementById('recordButton');
    const recordingStatus = document.getElementById('recordingStatus');
    // Detect language from URL or default to chinese
    const language = window.location.pathname.includes('japanese') ? 'japanese' : 'chinese';
    const dynamicImage = document.getElementById('dynamic-image');
    
    // New elements for feedback
    const feedbackContainer = document.getElementById('feedback-container');
    const feedbackText = document.getElementById('feedback-text');
    
    if (!dynamicImage) {
        console.error('Dynamic image element not found');
        return;
    }
    
    const initialUrl = dynamicImage.src;
    let mediaRecorder;
    let audioChunks = [];
    let isRecording = false;

    // Play initial welcome audio
    playAudio(language + "_image");

    function playAudio(audioSource) {
        // If it's a full URL (from backend response), use it directly
        // Otherwise treat it as an ID for the /api/audio endpoint
        const src = audioSource.startsWith('/') || audioSource.startsWith('http') 
            ? audioSource 
            : `/api/audio/${audioSource}`;

        const audio = new Audio(src);
        audio.play().catch(error => console.error('Error playing audio:', error));
    }

    async function toggleRecording() {
        const sampleRate = 44100;
        const numChannels = 1;

        if (!isRecording) {
            // --- START RECORDING ---
            audioChunks = [];
            
            try {
                const stream = await navigator.mediaDevices.getUserMedia({
                    audio: {
                        sampleRate: sampleRate,
                        channelCount: numChannels,
                        echoCancellation: true,
                        noiseSuppression: true
                    }
                });

                mediaRecorder = new MediaRecorder(stream, {
                    mimeType: 'audio/webm', 
                    audioBitsPerSecond: 16 * sampleRate
                });

                mediaRecorder.ondataavailable = (event) => {
                    audioChunks.push(event.data);
                };

                mediaRecorder.onstop = async () => {
                    // UI: Processing State
                    const statusText = language === 'chinese' ? '思考中...' : '考え中...';
                    recordingStatus.textContent = statusText;
                    
                    // Hide old feedback while processing
                    if(feedbackContainer) feedbackContainer.style.display = 'none';

                    // Convert Audio
                    const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                    const wavBlob = await convertToWav(audioBlob, sampleRate, numChannels);

                    // Prepare Payload
                    const formData = new FormData();
                    formData.append('audio', wavBlob, 'recording.wav');
                    formData.append('language', language);
                    // Send current image URL so the VQA model knows what it's looking at
                    formData.append('image_url', dynamicImage.src); 

                    try {
                        const response = await fetch('/api/image_guess', {
                            method: 'POST',
                            body: formData
                        });

                        if (!response.ok) throw new Error('Network response was not ok');

                        const data = await response.json();

                        // 1. Update Image (if returned)
                        if (data.image) {
                            dynamicImage.src = `data:image/jpeg;base64,${data.image}`;
                        }

                        // 2. Show Text Feedback
                        if (data.answer_text && feedbackContainer) {
                            feedbackText.textContent = data.answer_text;
                            feedbackContainer.style.display = 'block';
                        }

                        // 3. Play Audio Response
                        if (data.audio_url) {
                            playAudio(data.audio_url);
                        }
                        
                        // Reset UI
                        const readyText = language === 'chinese' ? '准备就绪' : '準備ができて';
                        recordingStatus.textContent = readyText;

                    } catch (error) {
                        console.error('Error:', error);
                        recordingStatus.textContent = language === 'chinese' ? '错误' : 'エラー';
                    }
                };

                mediaRecorder.start(1000);
                isRecording = true;

                // Update UI to "Recording" state
                recordButton.classList.add('recording');
                const stopText = language === 'chinese' ? '停止' : '停止';
                recordButton.querySelector('.button-text').textContent = stopText;
                recordingStatus.textContent = language === 'chinese' ? '正在录音...' : '録音中...';

            } catch (error) {
                console.error('Error accessing microphone:', error);
                alert('Microphone access denied or not found.');
            }

        } else {
            // --- STOP RECORDING ---
            mediaRecorder.stop();
            isRecording = false;
            
            // Stop stream tracks to release mic
            mediaRecorder.stream.getTracks().forEach(track => track.stop());

            // Reset UI Button
            recordButton.classList.remove('recording');
            const startText = language === 'chinese' ? '按下开始录音' : 'クリックして録音開始';
            recordButton.querySelector('.button-text').textContent = startText;
        }
    }

    // --- Audio Helper Utilities ---
    async function convertToWav(audioBlob, sampleRate, numChannels) {
        const audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate });
        const arrayBuffer = await audioBlob.arrayBuffer();
        const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);
        return new Blob([createWavFile(audioBuffer, numChannels)], { type: 'audio/wav' });
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

    if (recordButton) {
        recordButton.addEventListener('click', toggleRecording);
    }
});