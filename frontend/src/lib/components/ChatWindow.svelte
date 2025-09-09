<script>
    import { onMount } from 'svelte';
    import { MessageCircle, Lightbulb, Shield, RotateCcw, Send, Plus } from 'lucide-svelte';
    import { ollamaStore, conversationStore, ollamaActions, conversationActions } from '$lib/stores/ollama.js';
    import { chat, createStreamingChat } from '$lib/api.js';
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
    
    // Get current model display name
    const currentModelName = $derived($ollamaStore.selectedModel || 'No model selected');
    
    // Check if thinking mode is active
    const isThinkingModeActive = $derived($ollamaStore.thinkingMode.enabled);
    
    // Check if we have any tools selected
    const hasSelectedTools = $derived($ollamaStore.tools.selected.length > 0);
    
    onMount(() => {
        // Scroll to bottom on mount
        scrollToBottom();
        
        // Check connection and load initial data
        ollamaActions.checkConnection();
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
        
        const userMessage = messageInput.trim();
        messageInput = '';
        
        // Check if model is selected
        if (!$ollamaStore.selectedModel) {
            const errorMessage = {
                id: Date.now().toString() + '_error',
                role: 'assistant',
                content: '⚠️ No model selected. Please select a model from the sidebar first.',
                timestamp: new Date().toISOString()
            };
            
            // Ensure we have a conversation to add the message to
            let conversationId = $conversationStore.currentId;
            if (!conversationId) {
                conversationId = await conversationActions.createConversation();
            }
            
            conversationActions.addMessage(conversationId, errorMessage);
            return;
        }
        
        // Ensure we have a current conversation
        let conversationId = $conversationStore.currentId;
        if (!conversationId) {
            conversationId = await conversationActions.createConversation();
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
            // Prepare messages for API
            const conversationMessages = messages.map(msg => ({
                role: msg.role,
                content: msg.content
            }));
            
            // Add the new user message
            conversationMessages.push({
                role: 'user',
                content: userMessage
            });
            
            // Prepare assistant message placeholder
            const assistantMessage = {
                id: Date.now().toString() + '_assistant',
                role: 'assistant',
                content: '',
                timestamp: new Date().toISOString()
            };
            
            conversationActions.addMessage(conversationId, assistantMessage);
            
            // Send request with current model and settings
            const response = await chat.send(conversationMessages, {
                model: $ollamaStore.selectedModel,
                systemMessage: currentConversation?.systemMessage || $ollamaStore.systemMessage,
                useSelectedTools: $ollamaStore.tools.enabled
            });
            
            if (response.message?.content) {
                // Update the assistant message with the response
                conversationActions.updateLastMessage(conversationId, response.message.content);
                
                // Auto-generate title if this is the first exchange
                if (conversationMessages.length === 2) { // User message + assistant response
                    const title = generateConversationTitle(userMessage, response.message.content);
                    conversationActions.updateConversationTitle(conversationId, title);
                }
            } else {
                throw new Error('Invalid response format from API');
            }
            
        } catch (error) {
            console.error('Chat error:', error);
            
            const errorMessage = {
                id: Date.now().toString() + '_error',
                role: 'assistant',
                content: `❌ Error: ${error.message || 'Failed to get response from the model'}`,
                timestamp: new Date().toISOString()
            };
            
            // Replace the empty assistant message with error message
            conversationActions.updateLastMessage(conversationId, errorMessage.content);
            conversationActions.setError(error);
        } finally {
            isGenerating = false;
            conversationActions.setLoading(false);
        }
    }
    
    function generateConversationTitle(userMessage, assistantResponse) {
        // Simple title generation based on first user message
        const words = userMessage.split(' ').slice(0, 6);
        let title = words.join(' ');
        if (words.length === 6) title += '...';
        return title.length > 50 ? title.substring(0, 47) + '...' : title;
    }
    
    async function sendMessageStreaming() {
        if (!messageInput.trim() || isGenerating) return;
        
        const userMessage = messageInput.trim();
        messageInput = '';
        
        // Check if model is selected
        if (!$ollamaStore.selectedModel) {
            const errorMessage = {
                id: Date.now().toString() + '_error',
                role: 'assistant',
                content: '⚠️ No model selected. Please select a model from the sidebar first.',
                timestamp: new Date().toISOString()
            };
            
            // Ensure we have a conversation to add the message to
            let conversationId = $conversationStore.currentId;
            if (!conversationId) {
                conversationId = await conversationActions.createConversation();
            }
            
            conversationActions.addMessage(conversationId, errorMessage);
            return;
        }
        
        // Ensure we have a current conversation
        let conversationId = $conversationStore.currentId;
        if (!conversationId) {
            conversationId = await conversationActions.createConversation();
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
            // Prepare COMPLETE conversation history for API
            const allMessages = [...messages, userMessageObj];
            
            // Create assistant message placeholder
            const assistantMessage = {
                id: Date.now().toString() + '_assistant',
                role: 'assistant',
                content: '',
                timestamp: new Date().toISOString()
            };
            
            conversationActions.addMessage(conversationId, assistantMessage);
            
            // Create streaming chat with proper parameters
            currentStream = await createStreamingChat(allMessages, {
                model: $ollamaStore.selectedModel,
                systemMessage: getSystemMessageWithToolInstructions(),
                useSelectedTools: $ollamaStore.tools.enabled && $ollamaStore.tools.selected.length > 0,
                thinkingMode: $ollamaStore.thinkingMode.enabled,
                thinkingLevel: $ollamaStore.thinkingMode.level
            });
            
            // Process streaming response
            let fullContent = '';
            for await (const chunk of currentStream.getIterator()) {
                if (chunk.message?.content) {
                    fullContent += chunk.message.content;
                    conversationActions.updateLastMessage(conversationId, fullContent);
                }
            }
            
            // Auto-generate title if this is the first exchange
            if (allMessages.length === 2) {
                const title = generateConversationTitle(userMessage, fullContent);
                conversationActions.updateConversationTitle(conversationId, title);
            }
            
        } catch (error) {
            console.error('Streaming chat error:', error);
            
            const errorContent = `❌ Error: ${error.message || 'Failed to get response from the model'}`;
            conversationActions.updateLastMessage(conversationId, errorContent);
            conversationActions.setError(error);
        } finally {
            isGenerating = false;
            conversationActions.setLoading(false);
            currentStream = null;
        }
    }
    
    // Enhanced system message with stronger tool instructions
    function getSystemMessageWithToolInstructions() {
        let systemMessage = currentConversation?.systemMessage || $ollamaStore.systemMessage || 'You are a helpful AI assistant.';
        
        // Add tool instructions if tools are enabled
        if ($ollamaStore.tools.enabled && $ollamaStore.tools.selected.length > 0) {
            const toolNames = $ollamaStore.tools.selected.map(tool => 
                typeof tool === 'string' ? tool : tool.function?.name || 'unknown'
            );
            
            systemMessage += `You are a helpful assistant with access to tools. Use them when appropriate.`;
  
        }
        
        return systemMessage;
    }
    
    function handleKeydown(event) {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            sendMessageStreaming(); // Changed from sendMessage() to sendMessageStreaming()
        }
    }
    
    function toggleToolsMenu() {
        showToolsMenu = !showToolsMenu;
    }
    
    async function handleToolAction(action) {
        showToolsMenu = false;
        
        switch (action) {
            case 'tools':
                // Toggle tools menu in sidebar
                break;
            case 'thinking':
                await ollamaActions.setThinkingMode(
                    !$ollamaStore.thinkingMode.enabled,
                    $ollamaStore.thinkingMode.level
                );
                break;
            case 'model':
                // Show model selector
                break;
            case 'refresh':
                await refreshChat();
                break;
        }
    }
    
    async function refreshChat() {
        // Stop any ongoing generation
        if (currentStream) {
            await currentStream.close();
            currentStream = null;
        }
        
        isGenerating = false;
        conversationActions.setLoading(false);
        
        // Create new conversation
        await conversationActions.createConversation();
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
</script>

<svelte:window on:click={handleClickOutside} />

<main class="chat-window" class:sidebar-expanded={sidebarExpanded}>
    <!-- Messages Container -->
    <div class="messages-container" bind:this={messagesContainer}>
        <div class="messages">
            {#if !$ollamaStore.isConnected}
                <div class="connection-warning">
                    <h3>⚠️ Not Connected</h3>
                    <p>Unable to connect to the Ollama server. Please make sure:</p>
                    <ul>
                        <li>Ollama server is running</li>
                        <li>FastAPI server is running</li>
                        <li>Check the connection settings in the sidebar</li>
                    </ul>
                </div>
            {:else if messages.length === 0}
                <div class="welcome-message">
                    <h2>Welcome to Rhea AI Chat</h2>
                    <p>Selected Model: <strong>{currentModelName}</strong></p>
                    {#if hasSelectedTools}
                        <p>Active Tools: <strong>{$ollamaStore.tools.selected.length}</strong></p>
                    {/if}
                    {#if isThinkingModeActive}
                        <p>Thinking Mode: <strong>{$ollamaStore.thinkingMode.level}</strong></p>
                    {/if}
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
                    disabled={isGenerating || !$ollamaStore.isConnected}
                    title="Tools and Options"
                >
                    <Plus size={20} />
                </button>
                
                {#if showToolsMenu}
                    <div class="tools-menu">
                        <button 
                            class="tool-item"
                            on:click={() => handleToolAction('tools')}
                        >
                            <MessageCircle size={16} />
                            Tools ({$ollamaStore.tools.selected.length})
                        </button>
                        
                        <button 
                            class="tool-item"
                            class:active={isThinkingModeActive}
                            on:click={() => handleToolAction('thinking')}
                        >
                            <Lightbulb size={16} />
                            Thinking Mode ({$ollamaStore.thinkingMode.level})
                        </button>
                        
                        <button 
                            class="tool-item"
                            on:click={() => handleToolAction('model')}
                        >
                            <Shield size={16} />
                            {currentModelName.length > 20 ? 
                                currentModelName.substring(0, 20) + '...' : 
                                currentModelName}
                        </button>
                        
                        <div class="menu-divider"></div>
                        
                        <button 
                            class="tool-item"
                            on:click={() => handleToolAction('refresh')}
                            disabled={isGenerating}
                        >
                            <RotateCcw size={16} />
                            New Chat
                        </button>
                    </div>
                {/if}
            </div>
            
            <textarea
                bind:value={messageInput}
                on:keydown={handleKeydown}
                placeholder={$ollamaStore.isConnected ? 
                    (currentModelName === 'No model selected' ? 
                        "Select a model first..." : 
                        "Type your message... (Press Enter to send, Shift+Enter for new line)") :
                    "Not connected to server..."}
                rows="1"
                disabled={isGenerating || !$ollamaStore.isConnected || currentModelName === 'No model selected'}
            ></textarea>
            
            <button 
                class="input-button send-button"
                on:click={sendMessageStreaming}
                disabled={!messageInput.trim() || isGenerating || !$ollamaStore.isConnected || currentModelName === 'No model selected'}
                title="Send Message"
            >
                <Send size={20} />
            </button>
        </div>
    </div>
</main>
