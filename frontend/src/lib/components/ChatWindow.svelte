<script>
    let { sidebarExpanded, currentView } = $props();
    
    // Mock messages for demo
    let messages = $state([
        {
            id: '1',
            role: 'user',
            content: 'Hello! Can you help me understand how neural networks work?',
            timestamp: new Date()
        },
        {
            id: '2',
            role: 'assistant',
            content: 'Hello! I\'d be happy to help you understand neural networks. Neural networks are computational models inspired by biological neural networks. They consist of interconnected nodes (neurons) organized in layers that process information.\n\nWould you like me to explain the basic components first, or would you prefer to start with a specific aspect?',
            timestamp: new Date()
        }
    ]);
    
    let messageInput = $state('');
    let isGenerating = $state(false);
    
    function sendMessage() {
        if (!messageInput.trim() || isGenerating) return;
        
        // Add user message
        messages.push({
            id: Date.now().toString(),
            role: 'user',
            content: messageInput,
            timestamp: new Date()
        });
        
        const userMessage = messageInput;
        messageInput = '';
        isGenerating = true;
        
        // Simulate AI response
        setTimeout(() => {
            messages.push({
                id: Date.now().toString(),
                role: 'assistant',
                content: 'This is a simulated response. The actual AI integration will be implemented soon!',
                timestamp: new Date()
            });
            isGenerating = false;
        }, 1000);
    }
    
    function handleKeydown(event) {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            sendMessage();
        }
    }
</script>

<main class="chat-window" class:sidebar-expanded={sidebarExpanded}>
    <!-- Quick Actions Bar -->
    <div class="quick-actions">
        <div class="quick-actions-left">
            <button class="quick-btn">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/>
                </svg>
                Tools
            </button>
            
            <button class="quick-btn">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/>
                </svg>
                Thinking
            </button>
            
            <button class="quick-btn">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
                </svg>
                llama3.2:3b
            </button>
        </div>
        
        <div class="quick-actions-right">
            <button class="quick-btn">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
                </svg>
                Refresh
            </button>
        </div>
    </div>
    
    <!-- Messages Container -->
    <div class="messages-container">
        <div class="messages">
            {#each messages as message}
                <div class="message {message.role}">
                    <div class="message-content">
                        <div class="message-text">{message.content}</div>
                        <div class="message-timestamp">
                            {message.timestamp.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
                        </div>
                    </div>
                </div>
            {/each}
            
            {#if isGenerating}
                <div class="message assistant generating">
                    <div class="message-content">
                        <div class="typing-indicator">
                            <span></span>
                            <span></span>
                            <span></span>
                        </div>
                    </div>
                </div>
            {/if}
        </div>
    </div>
    
    <!-- Input Area -->
    <div class="input-area">
        <div class="input-container">
            <textarea
                bind:value={messageInput}
                on:keydown={handleKeydown}
                placeholder="Type your message... (Press Enter to send, Shift+Enter for new line)"
                rows="1"
                disabled={isGenerating}
            ></textarea>
            
            <button 
                class="send-button"
                on:click={sendMessage}
                disabled={!messageInput.trim() || isGenerating}
            >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"/>
                </svg>
            </button>
        </div>
    </div>
</main>

<style>
    .chat-window {
        flex: 1;
        display: flex;
        flex-direction: column;
        height: 100vh;
        background: var(--bg-primary);
        overflow: hidden;
    }
    
    .quick-actions {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 12px 20px;
        border-bottom: 1px solid var(--border-primary);
        background: var(--bg-secondary);
        gap: 12px;
    }
    
    .quick-actions-left,
    .quick-actions-right {
        display: flex;
        gap: 8px;
    }
    
    .quick-btn {
        background: var(--bg-tertiary);
        border: 1px solid var(--border-primary);
        color: var(--text-secondary);
        padding: 6px 12px;
        border-radius: 6px;
        font-size: 13px;
        cursor: pointer;
        display: flex;
        align-items: center;
        gap: 6px;
        transition: all var(--transition-fast);
    }
    
    .quick-btn:hover {
        background: var(--bg-primary);
        color: var(--text-primary);
        border-color: var(--border-secondary);
    }
    
    .messages-container {
        flex: 1;
        overflow-y: auto;
        padding: 20px;
    }
    
    .messages {
        max-width: 800px;
        margin: 0 auto;
        display: flex;
        flex-direction: column;
        gap: 20px;
    }
    
    .message {
        display: flex;
    }
    
    .message.user {
        justify-content: flex-end;
    }
    
    .message.assistant {
        justify-content: flex-start;
    }
    
    .message-content {
        max-width: 70%;
        background: var(--chat-assistant-bg);
        padding: 16px 20px;
        border-radius: 18px;
        position: relative;
    }
    
    .message.user .message-content {
        background: var(--chat-user-bg);
        color: white;
    }
    
    .message-text {
        font-size: 15px;
        line-height: 1.5;
        white-space: pre-wrap;
        word-wrap: break-word;
    }
    
    .message-timestamp {
        font-size: 11px;
        opacity: 0.6;
        margin-top: 8px;
        text-align: right;
    }
    
    .message.user .message-timestamp {
        text-align: left;
    }
    
    .typing-indicator {
        display: flex;
        gap: 4px;
        align-items: center;
        padding: 8px 0;
    }
    
    .typing-indicator span {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: var(--text-secondary);
        animation: typing 1.4s ease-in-out infinite both;
    }
    
    .typing-indicator span:nth-child(1) { animation-delay: -0.32s; }
    .typing-indicator span:nth-child(2) { animation-delay: -0.16s; }
    .typing-indicator span:nth-child(3) { animation-delay: 0s; }
    
    @keyframes typing {
        0%, 80%, 100% {
            transform: scale(0);
            opacity: 0.5;
        }
        40% {
            transform: scale(1);
            opacity: 1;
        }
    }
    
    .input-area {
        padding: 20px;
        border-top: 1px solid var(--border-primary);
        background: var(--bg-secondary);
    }
    
    .input-container {
        max-width: 800px;
        margin: 0 auto;
        position: relative;
        display: flex;
        align-items: flex-end;
        gap: 12px;
    }
    
    .input-container textarea {
        flex: 1;
        background: var(--bg-primary);
        border: 1px solid var(--border-primary);
        border-radius: 12px;
        padding: 12px 16px;
        font-size: 15px;
        line-height: 1.5;
        resize: none;
        min-height: 44px;
        max-height: 150px;
        transition: border-color var(--transition-fast);
    }
    
    .input-container textarea:focus {
        border-color: var(--accent-primary);
        outline: none;
    }
    
    .input-container textarea:disabled {
        opacity: 0.5;
        cursor: not-allowed;
    }
    
    .send-button {
        background: var(--accent-primary);
        border: none;
        color: white;
        width: 44px;
        height: 44px;
        border-radius: 12px;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: all var(--transition-fast);
        flex-shrink: 0;
    }
    
    .send-button:hover:not(:disabled) {
        background: var(--accent-secondary);
        transform: translateY(-1px);
    }
    
    .send-button:disabled {
        opacity: 0.5;
        cursor: not-allowed;
        transform: none;
    }
    
    /* Responsive adjustments */
    @media (max-width: 768px) {
        .message-content {
            max-width: 85%;
        }
        
        .messages-container {
            padding: 16px;
        }
        
        .input-area {
            padding: 16px;
        }
        
        .quick-actions {
            padding: 8px 16px;
        }
        
        .quick-btn {
            padding: 4px 8px;
            font-size: 12px;
        }
    }
</style>