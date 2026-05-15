const form = document.getElementById('chat-form');
const input = document.getElementById('message-input');
const sendBtn = document.getElementById('send-button');
const messagesContainer = document.getElementById('chat-messages');

let messageHistory = [
    { role: "system", content: "You are a helpful, smart, and concise AI assistant, like ChatGPT." }
];

// Auto-resize textarea
input.addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = (this.scrollHeight) + 'px';
    sendBtn.disabled = this.value.trim() === '';
});

// Handle enter to submit
input.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        if (this.value.trim() !== '') {
            form.dispatchEvent(new Event('submit'));
        }
    }
});

function appendMessage(role, content) {
    const isUser = role === 'user';
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${!isUser ? 'system-message' : ''}`;
    
    // We'll parse markdown for AI, raw text for user
    const htmlContent = isUser ? escapeHTML(content) : marked.parse(content);

    messageDiv.innerHTML = `
        <div class="message-content">
            <div class="avatar ${isUser ? 'user-avatar' : 'ai-avatar'}">${isUser ? 'U' : 'AI'}</div>
            <div class="text">${htmlContent}</div>
        </div>
    `;
    
    messagesContainer.appendChild(messageDiv);
    scrollToBottom();
    return messageDiv.querySelector('.text');
}

function escapeHTML(str) {
    return str.replace(/[&<>'"]/g, 
        tag => ({
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            "'": '&#39;',
            '"': '&quot;'
        }[tag] || tag)
    );
}

function scrollToBottom() {
    messagesContainer.scrollTo({
        top: messagesContainer.scrollHeight,
        behavior: 'smooth'
    });
}

function showTypingIndicator() {
    const div = document.createElement('div');
    div.className = 'message system-message typing-indicator-msg';
    div.innerHTML = `
        <div class="message-content">
            <div class="avatar ai-avatar">AI</div>
            <div class="text typing-indicator">
                <span></span><span></span><span></span>
            </div>
        </div>
    `;
    messagesContainer.appendChild(div);
    scrollToBottom();
    return div;
}

form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const userMessage = input.value.trim();
    if (!userMessage) return;

    // Reset input
    input.value = '';
    input.style.height = 'auto';
    sendBtn.disabled = true;

    // Append user message
    appendMessage('user', userMessage);
    messageHistory.push({ role: 'user', content: userMessage });

    const indicator = showTypingIndicator();

    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ messages: messageHistory })
        });

        if (!response.ok) {
            throw new Error(`Server error: ${response.status}`);
        }

        // Remove indicator
        indicator.remove();

        // Create empty AI message box for streaming
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message system-message';
        messageDiv.innerHTML = `
            <div class="message-content">
                <div class="avatar ai-avatar">AI</div>
                <div class="text"></div>
            </div>
        `;
        messagesContainer.appendChild(messageDiv);
        const textContainer = messageDiv.querySelector('.text');
        
        let aiContent = "";
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');
        
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            const chunk = decoder.decode(value, { stream: true });
            
            // Assume SSE format from backend (data: ...\n\n)
            const lines = chunk.split('\n');
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const data = line.slice(6);
                    if (data === '[DONE]') continue;
                    
                    try {
                        const parsed = JSON.parse(data);
                        if (parsed.content) {
                            aiContent += parsed.content;
                            textContainer.innerHTML = marked.parse(aiContent);
                            scrollToBottom();
                        }
                    } catch (e) {
                         // Fallback if the backend sends raw content instead of JSON SSE
                        if(data.trim() !== '') {
                            // If it's pure text chunk (we might try sending pure chunks)
                            aiContent += data;
                            textContainer.innerHTML = marked.parse(aiContent);
                            scrollToBottom();
                        }
                    }
                } else if (!line.startsWith(':') && line.trim().length > 0) {
                    // Try parsing as simple chunk just in case
                    aiContent += line;
                    textContainer.innerHTML = marked.parse(aiContent);
                    scrollToBottom();
                }
            }
        }
        
        messageHistory.push({ role: 'assistant', content: aiContent });

    } catch (err) {
        console.error(err);
        indicator.remove();
        appendMessage('assistant', '⚠️ Sorry, there was an error processing your request.');
    }
});

document.getElementById('new-chat-btn').addEventListener('click', () => {
    messagesContainer.innerHTML = '';
    messageHistory = [
        { role: "system", content: "You are a helpful, smart, and concise AI assistant, like ChatGPT." }
    ];
    appendMessage('assistant', 'Hello! How can I help you today?');
});
