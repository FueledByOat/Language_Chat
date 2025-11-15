document.addEventListener('DOMContentLoaded', function () {
    const recordButton = document.getElementById('recordButton');
    const recordingStatus = document.getElementById('recordingStatus');
    const language = window.location.pathname.includes('chinese') ? 'chinese' : 'japanese';
    const dynamicImage = document.getElementById('dynamic-image');
    
    if (!dynamicImage) {
        console.error('Dynamic image element not found');
        return;
    }
    
    const url = dynamicImage.src;

    let mediaRecorder;
    let audioChunks = [];
    let isRecording = false;

    // Ask the user what they see by playing the sound
    playAudio(language + "_image");

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
            });
    }

    // Function to handle voice recording
    async function toggleRecording() {
        const sampleRate = 44100;
        const numChannels = 1;

        if (!isRecording) {
            // Start recording
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
                    // Show loading state
                    const statusText = language === 'chinese' ? '处理中...' : '処理中...';
                    recordingStatus.textContent = statusText;

                    // Convert to WAV format
                    const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                    const wavBlob = await convertToWav(audioBlob, sampleRate, numChannels);

                    // Create form data
                    const formData = new FormData();
                    formData.append('audio', wavBlob, 'recording.wav');
                    formData.append('language', language);
                    formData.append('image_url', url);

                    try {
                        // Send audio to backend
                        const response = await fetch('/api/image_guess', {
                            method: 'POST',
                            body: formData
                        });

                        if (!response.ok) {
                            throw new Error('Network response was not ok');
                        }

                        const data = await response.json();

                        // Update image
                        const imgElement = document.getElementById('dynamic-image');
                        imgElement.src = `data:image/jpeg;base64,${data.image}`;
                        
                        // Reset status
                        const readyText = language === 'chinese' ? '准备就绪' : '準備ができて';
                        recordingStatus.textContent = readyText;

                    } catch (error) {
                        console.error('Error:', error);
                        const errorText = language === 'chinese' ? '发生错误，请重试' : 'エラーが発生しました';
                        recordingStatus.textContent = errorText;
                    }
                };

                mediaRecorder.start(1000);
                isRecording = true;

                // Update UI
                recordButton.classList.add('recording');
                const stopText = language === 'chinese' ? '点击停止录音' : '録音を停止';
                recordButton.querySelector('.button-text').textContent = stopText;
                const recordingText = language === 'chinese' ? '正在录音...' : '録音中...';
                recordingStatus.textContent = recordingText;

            } catch (error) {
                console.error('Error accessing microphone:', error);
                const micErrorText = language === 'chinese' 
                    ? '无法访问麦克风。请确保您已授予麦克风权限。'
                    : 'マイクにアクセスできません。マイクの権限を確認してください。';
                alert(micErrorText);
            }

        } else {
            // Stop recording
            mediaRecorder.stop();
            isRecording = false;

            // Stop all tracks
            mediaRecorder.stream.getTracks().forEach(track => track.stop());

            // Update UI
            recordButton.classList.remove('recording');
            const startText = language === 'chinese' ? '按下开始录音' : 'クリックして録音開始';
            recordButton.querySelector('.button-text').textContent = startText;
            const processingText = language === 'chinese' ? '正在处理...' : '処理中...';
            recordingStatus.textContent = processingText;
        }
    }

    // Helper function to convert audio blob to WAV format
    async function convertToWav(audioBlob, sampleRate, numChannels) {
        const audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate });
        const arrayBuffer = await audioBlob.arrayBuffer();
        const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);
        const wavBuffer = createWavFile(audioBuffer, numChannels);
        return new Blob([wavBuffer], { type: 'audio/wav' });
    }

    // Function to create WAV file from audio buffer
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

        // Write WAV header
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

        // Write audio data
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

    // Helper function to write strings to DataView
    function writeString(view, offset, string) {
        for (let i = 0; i < string.length; i++) {
            view.setUint8(offset + i, string.charCodeAt(i));
        }
    }

    // Event listener for record button
    if (recordButton) {
        recordButton.addEventListener('click', toggleRecording);
    } else {
        console.error('Record button not found');
    }
});