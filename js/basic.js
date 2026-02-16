// Copyright (c) Microsoft. All rights reserved.
// Licensed under the MIT license.

// Global objects
var avatarSynthesizer
var peerConnection
var useTcpForWebRTC = false
var previousAnimationFrameTimestamp = 0;
var currentSpokenText = ''; // Store current spoken text for subtitles

// Session persistence
let isSessionActive = false;

// Retry configuration for throttling
const RETRY_CONFIG = {
    maxRetries: 3,
    initialDelay: 2000,  // 2 seconds
    maxDelay: 10000,     // 10 seconds
    backoffMultiplier: 2
};
let currentRetryCount = 0;

// Auto-start session on page load
document.addEventListener('DOMContentLoaded', async () => {
    // Clear any old localStorage
    localStorage.clear();
    
    // Note: API Key and Region should be configured in index.html
    // Update the hidden inputs in index.html with your Azure Speech credentials
    
    const apiKey = document.getElementById('APIKey').value;
    const region = document.getElementById('region').value;
    
    if (!apiKey) {
        log('❌ No API key found.');
        return;
    }
    
    log(`✅ Region: ${region}`);
    log(`✅ API Key: ${apiKey.substring(0, 10)}...`);
    
    // Session ready but not auto-started
    log('💡 Click "Start Session" to begin');
});

// Close session when page unloads to release Azure resources
window.addEventListener('beforeunload', () => {
    if (avatarSynthesizer) {
        try {
            avatarSynthesizer.stopAvatarAsync();
            avatarSynthesizer.close();
        } catch (e) {
            console.log('Cleanup error:', e);
        }
    }
    if (peerConnection) {
        try {
            peerConnection.close();
        } catch (e) {
            console.log('Cleanup error:', e);
        }
    }
});

// Logger - Disabled for production
const log = msg => {
    // document.getElementById('logging').innerHTML += msg + '<br>'
}

// Retry helper with exponential backoff
async function retryWithBackoff(fn, retryCount = 0) {
    try {
        return await fn();
    } catch (error) {
        // Check if it's a throttling error (4429)
        const isThrottling = error.toString().includes('4429') || 
                           error.toString().includes('throttle') ||
                           error.toString().includes('concurrent request limit');
        
        if (isThrottling && retryCount < RETRY_CONFIG.maxRetries) {
            const delay = Math.min(
                RETRY_CONFIG.initialDelay * Math.pow(RETRY_CONFIG.backoffMultiplier, retryCount),
                RETRY_CONFIG.maxDelay
            );
            
            log(`⚠️ Service throttled (attempt ${retryCount + 1}/${RETRY_CONFIG.maxRetries}). Retrying in ${delay/1000}s...`);
            
            await new Promise(resolve => setTimeout(resolve, delay));
            return retryWithBackoff(fn, retryCount + 1);
        }
        
        throw error;
    }
}

// Setup WebRTC
function setupWebRTC(iceServerUrl, iceServerUsername, iceServerCredential) {
    // Create WebRTC peer connection
    peerConnection = new RTCPeerConnection({
        iceServers: [{
            urls: [ useTcpForWebRTC ? iceServerUrl.replace(':3478', ':443?transport=tcp') : iceServerUrl ],
            username: iceServerUsername,
            credential: iceServerCredential
        }],
        iceTransportPolicy: useTcpForWebRTC ? 'relay' : 'all'
    })

    // Fetch WebRTC video stream and mount it to an HTML video element
    peerConnection.ontrack = function (event) {
        // Clean up existing video element if there is any
        remoteVideoDiv = document.getElementById('remoteVideo')
        for (var i = 0; i < remoteVideoDiv.childNodes.length; i++) {
            if (remoteVideoDiv.childNodes[i].localName === event.track.kind) {
                remoteVideoDiv.removeChild(remoteVideoDiv.childNodes[i])
            }
        }

        const mediaPlayer = document.createElement(event.track.kind)
        mediaPlayer.id = event.track.kind
        mediaPlayer.srcObject = event.streams[0]
        mediaPlayer.autoplay = true
        mediaPlayer.playsInline = true
        
        // Audio should NOT be muted, video can be muted
        if (event.track.kind === 'audio') {
            mediaPlayer.muted = false;
            mediaPlayer.volume = 1.0;
        } else {
            mediaPlayer.muted = true;
        }
        
        mediaPlayer.addEventListener('loadeddata', () => {
            mediaPlayer.play().catch(err => {
                console.log('Autoplay issue, retrying:', err);
                // Retry unmuted for audio
                if (event.track.kind === 'audio') {
                    setTimeout(() => {
                        mediaPlayer.muted = false;
                        mediaPlayer.play().catch(e => console.log('Audio play failed:', e));
                    }, 100);
                }
            });
        })

        document.getElementById('remoteVideo').appendChild(mediaPlayer)
        document.getElementById('videoLabel').hidden = false
        document.getElementById('overlayArea').hidden = false
        
        console.log(`📺 Media track added: ${event.track.kind}, readyState: ${event.track.readyState}`);
        console.log(`📺 Stream active: ${event.streams[0].active}, tracks: ${event.streams[0].getTracks().length}`);

        if (event.track.kind === 'video') {
            mediaPlayer.playsInline = true
            remoteVideoDiv = document.getElementById('remoteVideo')
            canvas = document.getElementById('canvas')
            
            // Log video metadata when loaded
            mediaPlayer.addEventListener('loadedmetadata', () => {
                console.log(`✅ Video loaded: ${mediaPlayer.videoWidth}x${mediaPlayer.videoHeight}`);
                console.log(`✅ Video element dimensions: ${mediaPlayer.clientWidth}x${mediaPlayer.clientHeight}`);
            });
            
            // Log when video starts playing
            mediaPlayer.addEventListener('playing', () => {
                console.log(`▶️ Video is now playing`);
            });
            
            // Log any errors
            mediaPlayer.addEventListener('error', (e) => {
                console.error(`❌ Video error:`, mediaPlayer.error);
            });

            mediaPlayer.addEventListener('play', () => {
                mediaPlayer.style.width = (mediaPlayer.videoWidth / 2) + 'px'
                mediaPlayer.style.height = 'auto'
            })
        }
        // Audio is already configured above (lines 108-110) with muted=false
    }

    // Listen to data channel, to get the event from the server
    peerConnection.addEventListener("datachannel", event => {
        const dataChannel = event.channel
        dataChannel.onmessage = e => {
            let subtitles = document.getElementById('subtitles')
            const webRTCEvent = JSON.parse(e.data)
            if (webRTCEvent.event.eventType === 'EVENT_TYPE_TURN_START' && document.getElementById('showSubtitles').checked) {
                subtitles.hidden = false
                subtitles.innerHTML = currentSpokenText || 'Speaking...'
            } else if (webRTCEvent.event.eventType === 'EVENT_TYPE_SESSION_END' || webRTCEvent.event.eventType === 'EVENT_TYPE_SWITCH_TO_IDLE') {
                subtitles.hidden = true
            }
            console.log("[" + (new Date()).toISOString() + "] WebRTC event received: " + e.data)
        }
    })

    // This is a workaround to make sure the data channel listening is working by creating a data channel from the client side
    c = peerConnection.createDataChannel("eventChannel")

    // Make necessary update to the web page when the connection state changes
    peerConnection.oniceconnectionstatechange = e => {
        log("WebRTC status: " + peerConnection.iceConnectionState)
        console.log("🔍 ICE Connection State:", peerConnection.iceConnectionState)

        if (peerConnection.iceConnectionState === 'connected' || peerConnection.iceConnectionState === 'completed') {
            console.log("✅ WebRTC Connected! Enabling buttons...")
            isSessionActive = true;
            localStorage.setItem('avatarSessionActive', 'true');
            
            // Update session status
            const statusEl = document.getElementById('statusText');
            if (statusEl) statusEl.textContent = '✅ Avatar session active';
            
            // Ensure audio element is unmuted and playing
            setTimeout(() => {
                const audioElement = document.getElementById('audio');
                if (audioElement) {
                    audioElement.muted = false;
                    audioElement.volume = 1.0;
                    audioElement.play().catch(e => console.log('Audio autoplay:', e));
                    console.log('🔊 Audio unmuted and ready');
                }
            }, 500);
            
            // Enable chat send button
            const sendChatBtn = document.getElementById('sendChat');
            if (sendChatBtn) {
                sendChatBtn.disabled = false;
                log('✅ Avatar ready! You can now chat');
            }
            
            // Enable push-to-talk button
            const pttBtn = document.getElementById('pushToTalk');
            if (pttBtn) {
                pttBtn.disabled = false;
            }
            
            // Configuration always visible in persistent mode
        }

        if (peerConnection.iceConnectionState === 'disconnected' || peerConnection.iceConnectionState === 'failed') {
            console.log("❌ WebRTC Disconnected/Failed")
            isSessionActive = false;
            localStorage.setItem('avatarSessionActive', 'false');
            
            // Disable chat send button
            const sendChatBtn = document.getElementById('sendChat');
            if (sendChatBtn) {
                sendChatBtn.disabled = true;
            }
            
            // Disable push-to-talk button
            const pttBtn = document.getElementById('pushToTalk');
            if (pttBtn) {
                pttBtn.disabled = true;
            }
            
            document.getElementById('stopSpeaking').disabled = true
            
            // Update status for disconnection
            const statusEl = document.getElementById('statusText');
            if (statusEl) statusEl.textContent = '⚠️ Session disconnected - Click Restart Session';
            
            // Configuration always visible in persistent mode
        }
    }

    // Offer to receive 1 audio, and 1 video track
    peerConnection.addTransceiver('video', { direction: 'sendrecv' })
    peerConnection.addTransceiver('audio', { direction: 'sendrecv' })

    // start avatar with retry logic for throttling
    const startAvatarWithRetry = async () => {
        return new Promise((resolve, reject) => {
            avatarSynthesizer.startAvatarAsync(peerConnection).then((r) => {
                if (r.reason === SpeechSDK.ResultReason.SynthesizingAudioCompleted) {
                    console.log("[" + (new Date()).toISOString() + "] Avatar started. Result ID: " + r.resultId)
                    currentRetryCount = 0; // Reset retry count on success
                    resolve(r);
                } else {
                    console.log("[" + (new Date()).toISOString() + "] Unable to start avatar. Result ID: " + r.resultId)
                    if (r.reason === SpeechSDK.ResultReason.Canceled) {
                        let cancellationDetails = SpeechSDK.CancellationDetails.fromResult(r)
                        if (cancellationDetails.reason === SpeechSDK.CancellationReason.Error) {
                            console.log(cancellationDetails.errorDetails)
                            reject(new Error(cancellationDetails.errorDetails));
                        };
                    }
                    reject(new Error("Avatar start failed"));
                }
            }).catch((error) => {
                console.log("[" + (new Date()).toISOString() + "] Avatar failed to start. Error: " + error)
                reject(error);
            });
        });
    };
    
    // Execute with retry
    retryWithBackoff(startAvatarWithRetry, currentRetryCount)
        .then(() => {
            log('✅ Avatar session started successfully');
            const statusEl = document.getElementById('statusText');
            if (statusEl) statusEl.textContent = '✅ Avatar session ready';
        })
        .catch((error) => {
            log("❌ Unable to start avatar after retries: " + error.message);
            const statusEl = document.getElementById('statusText');
            if (statusEl) statusEl.textContent = '❌ Failed to start - Click Restart Session';
        });
}

// Do HTML encoding on given text
function htmlEncode(text) {
    const entityMap = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;',
        '/': '&#x2F;'
    };

    return String(text).replace(/[&<>"'\/]/g, (match) => entityMap[match])
}

window.startSession = (isRestoring = false) => {
    log('🚀 Starting avatar session...');
    
    // Update status
    const statusEl = document.getElementById('statusText');
    if (statusEl) statusEl.textContent = '⏳ Connecting to avatar service...';
    
    // Only clear chat history when starting a NEW session (not restoring)
    if (!isRestoring && window.clearChatHistory) {
        window.clearChatHistory();
    }
    
    const cogSvcRegion = document.getElementById('region').value
    const cogSvcSubKey = document.getElementById('APIKey').value
    if (cogSvcSubKey === '' || cogSvcSubKey === null || cogSvcSubKey === undefined) {
        log('❌ No Speech Service credentials available')
        log('⚠️ Please check backend configuration or restart the server')
        alert('Speech Service credentials not loaded. Please check the backend logs and restart.')
        return
    }

    log(`🔑 Using credentials for region: ${cogSvcRegion}`)
    
    const privateEndpointEnabled = document.getElementById('enablePrivateEndpoint').checked
    const privateEndpoint = document.getElementById('privateEndpoint').value.slice(8)
    if (privateEndpointEnabled && privateEndpoint === '') {
        alert('Please fill in the Azure Speech endpoint.')
        return
    }

    let speechSynthesisConfig
    if (privateEndpointEnabled) {
        speechSynthesisConfig = SpeechSDK.SpeechConfig.fromEndpoint(new URL(`wss://${privateEndpoint}/tts/cognitiveservices/websocket/v1?enableTalkingAvatar=true`), cogSvcSubKey) 
    } else {
        speechSynthesisConfig = SpeechSDK.SpeechConfig.fromSubscription(cogSvcSubKey, cogSvcRegion)
    }
    speechSynthesisConfig.endpointId = document.getElementById('customVoiceEndpointId').value

    const videoFormat = new SpeechSDK.AvatarVideoFormat()
    let videoCropTopLeftX = document.getElementById('videoCrop').checked ? 600 : 0
    let videoCropBottomRightX = document.getElementById('videoCrop').checked ? 1320 : 1920
    videoFormat.setCropRange(new SpeechSDK.Coordinate(videoCropTopLeftX, 0), new SpeechSDK.Coordinate(videoCropBottomRightX, 1080));

    const talkingAvatarCharacter = document.getElementById('talkingAvatarCharacter').value
    const talkingAvatarStyle = document.getElementById('talkingAvatarStyle').value
    const avatarConfig = new SpeechSDK.AvatarConfig(talkingAvatarCharacter, talkingAvatarStyle, videoFormat)
    avatarConfig.customized = document.getElementById('customizedAvatar').checked
    avatarConfig.useBuiltInVoice = document.getElementById('useBuiltInVoice').checked 
    avatarConfig.backgroundColor = document.getElementById('backgroundColor').value
    avatarConfig.backgroundImage = document.getElementById('backgroundImageUrl').value
    
    const xhr = new XMLHttpRequest()
    if (privateEndpointEnabled) {
        xhr.open("GET", `https://${privateEndpoint}/tts/cognitiveservices/avatar/relay/token/v1`)
    } else {
        xhr.open("GET", `https://${cogSvcRegion}.tts.speech.microsoft.com/cognitiveservices/avatar/relay/token/v1`)
    }
    xhr.setRequestHeader("Ocp-Apim-Subscription-Key", cogSvcSubKey)
    xhr.addEventListener("readystatechange", function() {
        if (this.readyState === 4) {
            const responseData = JSON.parse(this.responseText)
            const iceServerUrl = responseData.Urls[0]
            const iceServerUsername = responseData.Username
            const iceServerCredential = responseData.Password

            avatarConfig.remoteIceServers = [{
                urls: [ iceServerUrl ],
                username: iceServerUsername,
                credential: iceServerCredential
            }]

            avatarSynthesizer = new SpeechSDK.AvatarSynthesizer(speechSynthesisConfig, avatarConfig)
            avatarSynthesizer.avatarEventReceived = function (s, e) {
                var offsetMessage = ", offset from session start: " + e.offset / 10000 + "ms."
                if (e.offset === 0) {
                    offsetMessage = ""
                }
                console.log("[" + (new Date()).toISOString() + "] Event received: " + e.description + offsetMessage)
            }

            setupWebRTC(iceServerUrl, iceServerUsername, iceServerCredential)
        }
    })
    xhr.send()
    
}

window.speakText = (text) => {
    // Check if avatar session is active
    if (!avatarSynthesizer) {
        log('⚠️ Avatar session not started. Cannot speak.');
        return;
    }
    
    if (!text || text.trim() === '') {
        log('⚠️ No text to speak');
        return;
    }
    
    // Store globally for subtitles
    window.currentSpokenText = text;
    
    // Enable stop speaking button
    const stopBtn = document.getElementById('stopSpeaking');
    if (stopBtn) stopBtn.disabled = false;
    
    // Ensure audio is unmuted
    const audioEl = document.getElementById('audio');
    if (audioEl) audioEl.muted = false;
    
    let ttsVoice = document.getElementById('ttsVoice').value;
    let spokenSsml = `<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xmlns:mstts='http://www.w3.org/2001/mstts' xml:lang='en-US'><voice name='${ttsVoice}'><mstts:leadingsilence-exact value='0'/>${htmlEncode(text)}</voice></speak>`;
    
    console.log("[" + (new Date()).toISOString() + "] Speak request sent.");
    log(`🗣️ Avatar speaking: "${text.substring(0, 50)}${text.length > 50 ? '...' : ''}"`);
    
    avatarSynthesizer.speakSsmlAsync(spokenSsml).then(
        (result) => {
            if (stopBtn) stopBtn.disabled = true;
            if (result.reason === SpeechSDK.ResultReason.SynthesizingAudioCompleted) {
                console.log("[" + (new Date()).toISOString() + "] Speech synthesized successfully. Result ID: " + result.resultId);
            } else {
                console.log("[" + (new Date()).toISOString() + "] Unable to speak text. Result ID: " + result.resultId);
                if (result.reason === SpeechSDK.ResultReason.Canceled) {
                    let cancellationDetails = SpeechSDK.CancellationDetails.fromResult(result);
                    console.log(cancellationDetails.reason);
                    if (cancellationDetails.reason === SpeechSDK.CancellationReason.Error) {
                        console.log(cancellationDetails.errorDetails);
                    }
                }
            }
        }).catch((error) => {
            log(`❌ Speech error: ${error}`);
            if (stopBtn) stopBtn.disabled = true;
        });
};

window.stopSpeaking = () => {
    document.getElementById('stopSpeaking').disabled = true

    avatarSynthesizer.stopSpeakingAsync().then(
        log("[" + (new Date()).toISOString() + "] Stop speaking request sent.")
    ).catch(log);
}

window.restartSession = async () => {
    log('🔄 Restarting avatar session with new configuration...');
    
    // Update status
    const statusEl = document.getElementById('statusText');
    if (statusEl) statusEl.textContent = '🔄 Restarting session...';
    
    // Clear chat history
    if (window.clearChatHistory) {
        window.clearChatHistory();
    }
    
    // Stop current session if exists
    if (avatarSynthesizer || peerConnection) {
        log('🛑 Stopping current session...');
        
        // Stop avatar first to release server resources
        if (avatarSynthesizer) {
            try {
                await avatarSynthesizer.stopAvatarAsync();
                log('✅ Avatar session stopped on server');
            } catch (error) {
                console.log('Error stopping avatar:', error);
            }
            
            try {
                avatarSynthesizer.close();
            } catch (error) {
                console.log('Error closing synthesizer:', error);
            }
            avatarSynthesizer = null;
        }
        
        // Close peer connection
        if (peerConnection) {
            try {
                peerConnection.close();
            } catch (error) {
                console.log('Error closing peer connection:', error);
            }
            peerConnection = null;
        }
        
        // Clear video
        const remoteVideoDiv = document.getElementById('remoteVideo');
        if (remoteVideoDiv) {
            remoteVideoDiv.innerHTML = '';
        }
    }
    
    // Reset retry counter
    currentRetryCount = 0;
    
    // Wait a bit then start new session
    setTimeout(() => {
        log('🚀 Starting new session with updated configuration...');
        window.startSession(false); // false = don't restore, start fresh
    }, 500);
};

window.stopSession = () => {
    log('🛑 Stopping avatar session...');
    
    // Mark session as inactive
    isSessionActive = false;
    localStorage.setItem('avatarSessionActive', 'false');
    
    // Reset retry counter
    currentRetryCount = 0;
    
    const sendChatBtn = document.getElementById('sendChat');
    if (sendChatBtn) sendChatBtn.disabled = true;
    
    document.getElementById('stopSpeaking').disabled = true;
    
    // Update status
    const statusEl = document.getElementById('statusText');
    if (statusEl) statusEl.textContent = '⏹️ Session stopped';
    
    // Close avatar synthesizer
    if (avatarSynthesizer) {
        try {
            // Stop avatar on server to release resources
            avatarSynthesizer.stopAvatarAsync().then(() => {
                log('✅ Avatar session stopped on server');
            }).catch(error => {
                console.log('Error stopping avatar:', error);
            });
            
            avatarSynthesizer.close();
        } catch (error) {
            console.log('Error closing synthesizer:', error);
        }
        avatarSynthesizer = null;
    }
    
    // Close peer connection
    if (peerConnection) {
        try {
            peerConnection.close();
        } catch (error) {
            console.log('Error closing peer connection:', error);
        }
        peerConnection = null;
    }
    
    // Clear video element
    const remoteVideoDiv = document.getElementById('remoteVideo');
    if (remoteVideoDiv) {
        remoteVideoDiv.innerHTML = '';
    }
    
    // Configuration always visible in persistent mode
    document.getElementById('videoLabel').hidden = false;
    
    log('✅ Session stopped successfully');
}

window.updatePrivateEndpoint = () => {
    if (document.getElementById('enablePrivateEndpoint').checked) {
        document.getElementById('showPrivateEndpointCheckBox').hidden = false
    } else {
        document.getElementById('showPrivateEndpointCheckBox').hidden = true
    }
}

window.updateCustomAvatarBox = () => {
    if (document.getElementById('customizedAvatar').checked) {
        document.getElementById('useBuiltInVoice').disabled = false
    } else {
        document.getElementById('useBuiltInVoice').disabled = true
        document.getElementById('useBuiltInVoice').checked = false
    }
}

window.updateAvatarStyles = () => {
    const character = document.getElementById('talkingAvatarCharacter').value;
    const styleSelect = document.getElementById('talkingAvatarStyle');
    
    // Define available styles for each character
    const avatarStyles = {
        'harry': ['business', 'casual', 'youthful'],
        'jeff': ['business', 'formal'],
        'lisa': ['casual-sitting'],
        'lori': ['casual', 'formal', 'graceful'],
        'max': ['business', 'casual', 'formal'],
        'meg': ['business', 'casual', 'formal']
    };
    
    // Clear current options
    styleSelect.innerHTML = '';
    
    
    // Add available styles for selected character
    const styles = avatarStyles[character] || ['casual-sitting'];
    styles.forEach(style => {
        const option = document.createElement('option');
        option.value = style;
        option.textContent = style.charAt(0).toUpperCase() + style.slice(1).replace('-', ' ');
        styleSelect.appendChild(option);
    });
    
    // Save configuration when changed
    saveConfiguration();
}

// Speech-to-Text for Push-to-Talk
let speechRecognizer = null;
let isRecording = false;

window.startRecording = () => {
    if (isRecording || !isSessionActive) return;
    
    const region = document.getElementById('region').value;
    const apiKey = document.getElementById('APIKey').value;
    
    if (!region || !apiKey) {
        log('⚠️ Missing Speech API credentials');
        return;
    }
    
    try {
        const speechConfig = SpeechSDK.SpeechConfig.fromSubscription(apiKey, region);
        speechConfig.speechRecognitionLanguage = 'es-ES'; // Change as needed
        
        const audioConfig = SpeechSDK.AudioConfig.fromDefaultMicrophoneInput();
        speechRecognizer = new SpeechSDK.SpeechRecognizer(speechConfig, audioConfig);
        
        isRecording = true;
        const btn = document.getElementById('pushToTalk');
        if (btn) {
            btn.style.backgroundColor = '#dc3545';
            btn.textContent = '⏺️';
        }
        
        log('🎤 Recording...');
        
        speechRecognizer.recognizeOnceAsync(
            result => {
                if (result.reason === SpeechSDK.ResultReason.RecognizedSpeech) {
                    const text = result.text;
                    document.getElementById('chatInput').value = text;
                    log(`✅ Recognized: ${text}`);
                    
                    // Auto-send after recognition
                    setTimeout(() => window.sendChatMessage(), 100);
                } else if (result.reason === SpeechSDK.ResultReason.NoMatch) {
                    log('⚠️ No speech recognized');
                }
                
                window.stopRecording();
            },
            error => {
                log(`❌ Speech recognition error: ${error}`);
                window.stopRecording();
            }
        );
    } catch (error) {
        log(`❌ Failed to start recording: ${error}`);
        isRecording = false;
    }
};

window.stopRecording = () => {
    if (!isRecording) return;
    
    if (speechRecognizer) {
        speechRecognizer.close();
        speechRecognizer = null;
    }
    
    isRecording = false;
    const btn = document.getElementById('pushToTalk');
    if (btn) {
        btn.style.backgroundColor = '#28a745';
        btn.textContent = '🎤';
    }
};

