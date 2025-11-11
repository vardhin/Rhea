<script>
    import { onMount } from 'svelte';
    import { MessageCircle, Send, Plus, Square, Sparkles } from 'lucide-svelte';
    import { conversationStore, conversationActions } from '$lib/stores/store.js';
    import { askQuestionStreaming } from '$lib/tool-api.js';
    import './chatwindow.css';
    
    let { sidebarExpanded, currentView } = $props();
    
    let messageInput = $state('');
    let isGenerating = $state(false);
    let showToolsMenu = $state(false);
    let messagesContainer;
    let currentStream = null;
    
    // Get current conversation using $derived
    const currentConversation = $derived(
        $conversationStore.conversations.find(
            conv => conv.id === $conversationStore.currentId
        )
    );
    
    const messages = $derived(currentConversation?.messages || []);
    
    onMount(() => {
        // Scroll to bottom on mount
        scrollToBottom();
    });
    
    function scrollToBottom() {
        if (messagesContainer) {
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }
    }
    
    // Auto-scroll when messages change
    $effect(() => {
        if (messages.length > 0) {
            setTimeout(scrollToBottom, 50);
        }
    });

    async function sendMessage() {
        if (!messageInput.trim() || isGenerating) return;
        await sendMessageToolAgent();
    }

    // Tool Agent Mode - streams thinking process
    async function sendMessageToolAgent() {
        const userMessage = messageInput.trim();
        messageInput = '';
        
        // Ensure we have a current conversation
        let conversationId = $conversationStore.currentId;
        if (!conversationId) {
            conversationId = await conversationActions.create();
        }
        
        // Add user message
        const userMessageObj = {
            id: Date.now().toString(),
            role: 'user',
            content: userMessage,
            timestamp: new Date().toISOString()
        };
        
        conversationActions.addMessage(conversationId, userMessageObj);
        
        isGenerating = true;
        conversationActions.setLoading(true);
        
        try {
            // Create assistant message placeholder
            const assistantMessage = {
                id: Date.now().toString() + '_assistant',
                role: 'assistant',
                content: '',
                toolAgentSteps: [],
                timestamp: new Date().toISOString()
            };
            
            conversationActions.addMessage(conversationId, assistantMessage);
            
            // Stream from tool agent
            const stream = await askQuestionStreaming(userMessage);
            let fullContent = '';
            let agentSteps = [];
            
            for await (const message of stream) {
                console.log('Tool Agent Message:', message.type, message.data);
                
                switch (message.type) {
                    case 'start':
                        fullContent = '🔄 Starting...\n\n';
                        conversationActions.updateLastMessage(conversationId, fullContent);
                        break;
                        
                    case 'iteration':
                        fullContent += `\n**Iteration ${message.data.number}**\n`;
                        conversationActions.updateLastMessage(conversationId, fullContent);
                        break;
                        
                    case 'thinking':
                        fullContent += `🤔 ${message.data.message}\n`;
                        conversationActions.updateLastMessage(conversationId, fullContent);
                        break;
                        
                    case 'state':
                        fullContent += `\n📍 **State**: ${message.data.state}\n`;
                        fullContent += `💭 **Reasoning**: ${message.data.reasoning}\n`;
                        conversationActions.updateLastMessage(conversationId, fullContent);
                        
                        agentSteps.push({
                            type: 'state',
                            state: message.data.state,
                            reasoning: message.data.reasoning
                        });
                        break;
                        
                    case 'action':
                        if (message.data.action) {
                            fullContent += `🎯 **Action**: ${JSON.stringify(message.data.action, null, 2)}\n`;
                            conversationActions.updateLastMessage(conversationId, fullContent);
                        }
                        break;
                        
                    case 'result':
                        if (message.data.result) {
                            fullContent += `✅ **Result**: ${JSON.stringify(message.data.result, null, 2)}\n`;
                            conversationActions.updateLastMessage(conversationId, fullContent);
                        }
                        
                        agentSteps.push({
                            type: 'result',
                            state: message.data.state,
                            result: message.data.result
                        });
                        break;
                        
                    case 'final':
                        // CHANGED: Append final answer instead of replacing
                        fullContent += `\n\n---\n\n### 🎯 Final Answer\n\n${message.data.answer}\n\n`;
                        fullContent += `**Confidence**: ${message.data.confidence}\n`;
                        fullContent += `**Iterations**: ${message.data.iterations}\n`;
                        conversationActions.updateLastMessage(conversationId, fullContent);
                        break;
                        
                    case 'timeout':
                        fullContent += `\n\n⏱️ ${message.data.message}\n`;
                        conversationActions.updateLastMessage(conversationId, fullContent);
                        break;
                        
                    case 'error':
                        fullContent += `\n\n❌ Error: ${message.data.message}\n`;
                        conversationActions.updateLastMessage(conversationId, fullContent);
                        break;
                }
            }
            
            // Auto-generate title if this is the first exchange
            if (messages.length === 1) {
                const title = generateConversationTitle(userMessage, fullContent);
                conversationActions.updateConversationTitle(conversationId, title);
            }
            
        } catch (error) {
            console.error('Tool Agent error:', error);
            
            const errorContent = `❌ Error: ${error.message || 'Failed to get response from tool agent'}`;
            conversationActions.updateLastMessage(conversationId, errorContent);
            conversationActions.setError(error);
        } finally {
            isGenerating = false;
            conversationActions.setLoading(false);
            currentStream = null;
        }
    }
    
    function generateConversationTitle(userMessage, assistantResponse) {
        // Simple title generation based on first user message
        const words = userMessage.split(' ').slice(0, 6);
        let title = words.join(' ');
        if (words.length === 6) title += '...';
        return title.length > 50 ? title.substring(0, 47) + '...' : title;
    }
    
    function handleKeydown(event) {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            sendMessage();
        }
    }
    
    function toggleToolsMenu() {
        showToolsMenu = !showToolsMenu;
    }
    
    async function handleToolAction(action) {
        showToolsMenu = false;
        
        switch (action) {
            case 'refresh':
                await refreshChat();
                break;
        }
    }
    
    async function refreshChat() {
        // Stop any ongoing generation
        if (currentStream) {
            currentStream = null;
        }
        
        isGenerating = false;
        conversationActions.setLoading(false);
        
        // Create new conversation
        await conversationActions.create(); // Changed from createConversation to create
    }
    
    // Close menu when clicking outside
    function handleClickOutside(event) {
        if (showToolsMenu && !event.target.closest('.tools-menu-container')) {
            showToolsMenu = false;
        }
    }
    
    // Format timestamp for display
    function formatTimestamp(timestamp) {
        if (!timestamp) return '';
        const date = new Date(timestamp);
        return date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
    }
    
    async function stopGeneration() {
        if (currentStream) {
            currentStream = null;
        }
        
        isGenerating = false;
        conversationActions.setLoading(false);
        
        // Add a message indicating the generation was stopped
        if ($conversationStore.currentId) {
            const currentContent = messages[messages.length - 1]?.content || '';
            const stoppedMessage = currentContent + '\n\n[Generation stopped by user]';
            conversationActions.updateLastMessage($conversationStore.currentId, stoppedMessage);
        }
    }
</script>

<svelte:window on:click={handleClickOutside} />

<main class="chat-window" class:sidebar-expanded={sidebarExpanded}>
    <!-- Messages Container -->
    <div class="messages-container" bind:this={messagesContainer}>
        <div class="messages">
            {#if messages.length === 0}
                <div class="welcome-message">
                    <h2>Welcome to Rhea AI Chat</h2>
                    <p>Mode: <strong>🔧 Tool Agent (Gemini)</strong></p>
                    <p>The agent will automatically create and use tools to answer your questions.</p>
                    <p>Start a conversation by typing a message below.</p>
                </div>
            {:else}
                {#each messages as message}
                    <div class="message {message.role}">
                        <div class="message-content">
                            <div class="message-text">{message.content}</div>
                            
                            <div class="message-timestamp">
                                {formatTimestamp(message.timestamp)}
                            </div>
                        </div>
                    </div>
                {/each}
            {/if}
            
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
            
            {#if $conversationStore.error}
                <div class="error-message">
                    <strong>Error:</strong> {$conversationStore.error}
                </div>
            {/if}
        </div>
        <!-- Add padding at bottom to prevent overlap with floating input -->
        <div class="bottom-spacer"></div>
    </div>
    
    <!-- Floating Input Area -->
    <div class="input-area floating">
        <div class="input-container">
            <!-- Tools Menu Button -->
            <div class="tools-menu-container">
                <button 
                    class="input-button tools-button"
                    on:click={toggleToolsMenu}
                    disabled={isGenerating}
                    title="Tools and Options"
                >
                    <Plus size={20} />
                </button>
                
                {#if showToolsMenu}
                    <div class="tools-menu">
                        <button 
                            class="tool-item"
                            on:click={() => handleToolAction('refresh')}
                            disabled={isGenerating}
                        >
                            <MessageCircle size={16} />
                            New Chat
                        </button>
                    </div>
                {/if}
            </div>
            
            <textarea
                bind:value={messageInput}
                on:keydown={handleKeydown}
                placeholder="Ask anything - Tool Agent will handle it..."
                rows="1"
                disabled={isGenerating}
            ></textarea>
            
            <!-- Conditional rendering: Show stop button when generating, send button otherwise -->
            {#if isGenerating}
                <button 
                    class="input-button stop-button"
                    on:click={stopGeneration}
                    title="Stop Generation"
                >
                    <Square size={20} />
                </button>
            {:else}
                <button 
                    class="input-button send-button"
                    on:click={sendMessage}
                    disabled={!messageInput.trim() || isGenerating}
                    title="Send Message"
                >
                    <Send size={20} />
                </button>
            {/if}
        </div>
        
        <!-- Mode indicator -->
        <div class="mode-indicator">
            <Sparkles size={14} />
            Tool Agent Mode Active
        </div>
    </div>
</main>

<style>
    /* Add to your chatwindow.css */
.tool-calls {
    margin-top: 8px;
    padding: 8px;
    background: rgba(0, 123, 255, 0.1);
    border-radius: 6px;
    border-left: 3px solid var(--accent-primary);
}

.tool-calls-header {
    font-size: 12px;
    font-weight: 600;
    color: var(--accent-primary);
    margin-bottom: 6px;
}

.tool-call {
    margin-bottom: 4px;
}

.tool-call-name {
    font-size: 13px;
    font-weight: 500;
    color: var(--text-primary);
}

.tool-call-args {
    margin-top: 2px;
    font-size: 11px;
}

.tool-call-args code {
    background: rgba(0, 0, 0, 0.1);
    padding: 2px 4px;
    border-radius: 3px;
    font-family: monospace;
}

.stop-button {
    background-color: #dc3545;
    color: white;
    transition: all 0.2s ease;
}

.stop-button:hover:not(:disabled) {
    background-color: #c82333;
    transform: scale(1.05);
}

.stop-button:active {
    transform: scale(0.98);
}

/* Add animation for button transition */
.input-button {
    transition: all 0.2s ease;
}

.mode-indicator {
    position: absolute;
    top: -28px;
    left: 50%;
    transform: translateX(-50%);
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 4px 12px;
    background: rgba(124, 58, 237, 0.1);
    border: 1px solid rgba(124, 58, 237, 0.3);
    border-radius: 12px;
    font-size: 12px;
    font-weight: 500;
    color: #7c3aed;
}

.tool-item.active {
    background: rgba(124, 58, 237, 0.1);
    color: #7c3aed;
}
</style>
