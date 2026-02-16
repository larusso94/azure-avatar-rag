// RAG Integration for Azure Avatar
// Handles file upload, chat with knowledge base, and avatar integration

const API_BASE_URL = 'http://localhost:5001/api';
let conversationHistory = [];

// Load chat history from localStorage on page load
document.addEventListener('DOMContentLoaded', () => {
    loadChatHistory();
    loadDocumentsOnStart();
});

// Load chat history from localStorage
function loadChatHistory() {
    try {
        const saved = localStorage.getItem('avatarChatHistory');
        if (saved) {
            const messages = JSON.parse(saved);
            messages.forEach(msg => {
                addMessageToChat(msg.role, msg.content, false); // false = no save to avoid duplication
            });
            log(`✅ Loaded ${messages.length} messages from history`);
        }
    } catch (error) {
        console.error('Error loading chat history:', error);
    }
}

// Save chat history to localStorage
function saveChatHistory() {
    try {
        const chatHistory = document.getElementById('chatHistory');
        const messages = [];
        
        // Extract all messages from the DOM
        chatHistory.querySelectorAll('div[data-role]').forEach(msgDiv => {
            messages.push({
                role: msgDiv.dataset.role,
                content: msgDiv.dataset.content
            });
        });
        
        localStorage.setItem('avatarChatHistory', JSON.stringify(messages));
    } catch (error) {
        console.error('Error saving chat history:', error);
    }
}

// Clear chat history (called when starting new session)
window.clearChatHistory = () => {
    // Clear localStorage
    localStorage.removeItem('avatarChatHistory');
    
    // Clear conversation history
    conversationHistory = [];
    
    // Clear DOM
    const chatHistory = document.getElementById('chatHistory');
    if (chatHistory) {
        chatHistory.innerHTML = '';
    }
    
    log('🗑️ Chat history cleared for new session');
}

// Alias for restartChat button
window.restartChat = () => {
    log('🔄 Restarting chat (clearing history)...');
    window.clearChatHistory();
}

// Function to load documents on startup
async function loadDocumentsOnStart() {
    await loadDocuments();
}

// Upload document to knowledge base
window.uploadDocument = async () => {
    const fileInput = document.getElementById('fileUpload');
    const uploadStatus = document.getElementById('uploadStatus');
    const uploadBtn = document.getElementById('uploadBtn');
    
    if (!fileInput.files || fileInput.files.length === 0) {
        showUploadStatus('Please select a file', 'error');
        return;
    }
    
    const file = fileInput.files[0];
    const formData = new FormData();
    formData.append('file', file);
    
    uploadBtn.disabled = true;
    showUploadStatus('Uploading and processing...', 'info');
    
    try {
        const response = await fetch(`${API_BASE_URL}/upload`, {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (result.success) {
            showUploadStatus(
                `✅ Success! ${result.stored_chunks} chunks created from ${result.filename}`,
                'success'
            );
            fileInput.value = '';
            loadDocuments();
        } else {
            showUploadStatus(`❌ Error: ${result.error}`, 'error');
        }
    } catch (error) {
        showUploadStatus(`❌ Upload failed: ${error.message}`, 'error');
    } finally {
        uploadBtn.disabled = false;
    }
};

// Show upload status message
function showUploadStatus(message, type) {
    const uploadStatus = document.getElementById('uploadStatus');
    uploadStatus.textContent = message;
    uploadStatus.hidden = false;
    
    // Style based on type
    if (type === 'success') {
        uploadStatus.style.backgroundColor = '#d4edda';
        uploadStatus.style.color = '#155724';
        uploadStatus.style.border = '1px solid #c3e6cb';
    } else if (type === 'error') {
        uploadStatus.style.backgroundColor = '#f8d7da';
        uploadStatus.style.color = '#721c24';
        uploadStatus.style.border = '1px solid #f5c6cb';
    } else {
        uploadStatus.style.backgroundColor = '#d1ecf1';
        uploadStatus.style.color = '#0c5460';
        uploadStatus.style.border = '1px solid #bee5eb';
    }
    
    // Auto-hide after 5 seconds
    setTimeout(() => {
        uploadStatus.hidden = true;
    }, 5000);
}

// Load and display documents
async function loadDocuments() {
    const docsContainer = document.getElementById('docsContainer');
    
    try {
        const response = await fetch(`${API_BASE_URL}/documents`);
        const result = await response.json();
        
        if (result.success && result.documents.length > 0) {
            docsContainer.innerHTML = result.documents.map(doc => `
                <div style="padding: 5px; border-bottom: 1px solid #eee;">
                    📄 ${doc.filename || 'Unknown'} 
                    <span style="color: #666; font-size: 10px;">
                        (${new Date(doc.uploaded_at).toLocaleString()})
                    </span>
                </div>
            `).join('');
            log(`✅ Loaded ${result.documents.length} document(s) from knowledge base`);
        } else {
            docsContainer.innerHTML = '<p style="color: #666;">No documents uploaded yet</p>';
            log('ℹ️ Knowledge base is empty');
        }
    } catch (error) {
        console.error('Failed to load documents:', error);
        docsContainer.innerHTML = '<p style="color: #999;">⚠️ Backend not available. Upload documents to build knowledge base.</p>';
        log('⚠️ Could not connect to backend. Make sure the server is running on port 5001.');
    }
}

// Add message to chat history
function addMessageToChat(role, content, shouldSave = true) {
    const chatHistory = document.getElementById('chatHistory');
    
    // Create wrapper div that takes full width
    const wrapperDiv = document.createElement('div');
    wrapperDiv.style.width = '100%';
    wrapperDiv.style.marginBottom = '10px';
    wrapperDiv.style.display = 'flex';
    
    // Create message bubble with auto width
    const messageDiv = document.createElement('div');
    messageDiv.style.padding = '10px 15px';
    messageDiv.style.borderRadius = '18px';
    messageDiv.style.maxWidth = '70%';
    messageDiv.style.width = 'fit-content';
    messageDiv.style.wordWrap = 'break-word';
    
    // Store data attributes for persistence
    messageDiv.dataset.role = role;
    messageDiv.dataset.content = content;
    
    if (role === 'user') {
        // User message - blue bubble on the right, no label
        wrapperDiv.style.justifyContent = 'flex-end';
        messageDiv.style.backgroundColor = '#0078d4';
        messageDiv.style.color = 'white';
        messageDiv.innerHTML = content;
    } else {
        // Assistant message - gray bubble on the left with robot icon, no label
        wrapperDiv.style.justifyContent = 'flex-start';
        messageDiv.style.backgroundColor = '#f1f3f4';
        messageDiv.style.color = '#333';
        messageDiv.innerHTML = `🤖 ${content}`;
    }
    
    wrapperDiv.appendChild(messageDiv);
    chatHistory.appendChild(wrapperDiv);
    chatHistory.scrollTop = chatHistory.scrollHeight;
    
    // Save to localStorage
    if (shouldSave) {
        saveChatHistory();
    }
}

// Send chat message (always using RAG)
window.sendChatMessage = async () => {
    const chatInput = document.getElementById('chatInput');
    const sendBtn = document.getElementById('sendChat');
    const questionText = chatInput.value.trim();
    
    if (!questionText) {
        log('⚠️ Please enter a message');
        return;
    }
    
    // Add user message to chat
    addMessageToChat('user', questionText);
    chatInput.value = '';
    sendBtn.disabled = true;
    
    // Query knowledge base with RAG
    // showModeStatus('🤔 Thinking...', 'info'); // Removed: temporary message
    
    try {
        const response = await fetch(`${API_BASE_URL}/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                message: questionText,
                history: conversationHistory
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            const answer = result.response;
            
            // Update conversation history
            conversationHistory.push({ role: 'user', content: questionText });
            conversationHistory.push({ role: 'assistant', content: answer });
            
            // Keep only last 10 messages
            if (conversationHistory.length > 10) {
                conversationHistory = conversationHistory.slice(-10);
            }
            
            // Store text globally for subtitles
            window.currentSpokenText = answer;
            
            // showModeStatus('✅ Answer generated from knowledge base', 'success'); // Removed: temporary message
            log(`💬 Answer: ${answer}`);
            
            // Speak the answer using avatar synthesizer
            if (window.speakText) {
                window.speakText(answer);
            }
            
            // Add avatar response to chat after a small delay to avoid interrupting audio initialization
            setTimeout(() => {
                addMessageToChat('assistant', answer);
            }, 100);
        } else {
            const errorMsg = result.error || 'Unknown error';
            addMessageToChat('assistant', `❌ Error: ${errorMsg}`);
            showModeStatus(`❌ Error: ${errorMsg}`, 'error');
            log(`❌ Error: ${errorMsg}`);
        }
    } catch (error) {
        // Backend not available - fallback to direct speak
        const fallbackMsg = '⚠️ Backend unavailable, speaking your question...';
        addMessageToChat('assistant', fallbackMsg);
        // showModeStatus(fallbackMsg, 'warning'); // Removed: temporary message
        log(`⚠️ Backend not available: ${error.message}`);
        document.getElementById('spokenText').value = questionText;
        setTimeout(() => {
            window.speak();
        }, 1000);
    } finally {
        sendBtn.disabled = false;
    }
};

// Show mode status message
function showModeStatus(message, type) {
    const modeStatus = document.getElementById('modeStatus');
    modeStatus.textContent = message;
    modeStatus.hidden = false;
    
    // Style based on type
    if (type === 'success') {
        modeStatus.style.backgroundColor = '#d4edda';
        modeStatus.style.color = '#155724';
        modeStatus.style.border = '1px solid #c3e6cb';
    } else if (type === 'error') {
        modeStatus.style.backgroundColor = '#f8d7da';
        modeStatus.style.color = '#721c24';
        modeStatus.style.border = '1px solid #f5c6cb';
    } else if (type === 'warning') {
        modeStatus.style.backgroundColor = '#fff3cd';
        modeStatus.style.color = '#856404';
        modeStatus.style.border = '1px solid #ffeeba';
    } else {
        modeStatus.style.backgroundColor = '#d1ecf1';
        modeStatus.style.color = '#0c5460';
        modeStatus.style.border = '1px solid #bee5eb';
    }
    
    // Auto-hide after 5 seconds
    setTimeout(() => {
        modeStatus.hidden = true;
    }, 5000);
}

// Override the original startSession - button will be enabled by connection state change
const originalStartSession = window.startSession;
window.startSession = () => {
    originalStartSession();
    // Button will be enabled when connection state becomes 'connected'
};

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    loadDocuments();
    log('🤖 RAG system initialized. Upload documents to build knowledge base.');
});
