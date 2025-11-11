import { writable, get } from 'svelte/store';

// Local storage keys
const CONVERSATIONS_STORAGE_KEY = 'rhea_conversations';
const SIDEBAR_STORAGE_KEY = 'rhea_sidebar';

// Initial states
const initialConversationState = {
    conversations: [],
    currentId: null,
    isLoading: false,
    error: null
};

const initialSidebarState = {
    expanded: false,
    visible: true,
    currentView: 'chat' // 'chat' or 'agent-tools'
};

// Load from localStorage
function loadFromStorage(key, defaultValue) {
    if (typeof window === 'undefined') return defaultValue;
    
    try {
        const stored = localStorage.getItem(key);
        if (stored) {
            return JSON.parse(stored);
        }
    } catch (error) {
        console.error(`Failed to load ${key} from localStorage:`, error);
    }
    
    return defaultValue;
}

// Save to localStorage
function saveToStorage(key, data) {
    if (typeof window === 'undefined') return;
    
    try {
        localStorage.setItem(key, JSON.stringify(data));
    } catch (error) {
        console.error(`Failed to save ${key} to localStorage:`, error);
    }
}

// ==================== CONVERSATION STORE ====================

function createConversationStore() {
    const { subscribe, set, update } = writable(
        loadFromStorage(CONVERSATIONS_STORAGE_KEY, initialConversationState)
    );
    
    // Auto-save on any update
    subscribe(state => {
        saveToStorage(CONVERSATIONS_STORAGE_KEY, state);
    });
    
    return {
        subscribe,
        
        // Create new conversation
        create: (title = 'New Chat') => {
            const newConv = {
                id: Date.now().toString(),
                title,
                messages: [],
                timestamp: new Date().toISOString(),
                createdAt: new Date().toISOString(),
                updatedAt: new Date().toISOString()
            };
            
            update(state => {
                return {
                    ...state,
                    conversations: [newConv, ...state.conversations],
                    currentId: newConv.id
                };
            });
            
            return newConv.id;
        },
        
        // Select/switch to a conversation
        select: (id) => {
            update(state => ({
                ...state,
                currentId: id
            }));
        },
        
        // Delete conversation
        delete: (id) => {
            update(state => {
                const conversations = state.conversations.filter(c => c.id !== id);
                const currentId = state.currentId === id 
                    ? (conversations.length > 0 ? conversations[0].id : null)
                    : state.currentId;
                
                return {
                    ...state,
                    conversations,
                    currentId
                };
            });
        },
        
        // Update conversation title
        updateTitle: (id, title) => {
            update(state => ({
                ...state,
                conversations: state.conversations.map(conv => 
                    conv.id === id 
                        ? { 
                            ...conv, 
                            title, 
                            updatedAt: new Date().toISOString() 
                        }
                        : conv
                )
            }));
        },
        
        // Add message to conversation
        addMessage: (conversationId, message) => {
            update(state => ({
                ...state,
                conversations: state.conversations.map(conv => 
                    conv.id === conversationId
                        ? {
                            ...conv,
                            messages: [...conv.messages, message],
                            updatedAt: new Date().toISOString()
                        }
                        : conv
                )
            }));
        },
        
        // Update last message (for streaming)
        updateLastMessage: (conversationId, content, toolAgentSteps = null) => {
            update(state => ({
                ...state,
                conversations: state.conversations.map(conv => {
                    if (conv.id !== conversationId) return conv;
                    
                    const messages = [...conv.messages];
                    if (messages.length > 0) {
                        const lastMessage = messages[messages.length - 1];
                        messages[messages.length - 1] = {
                            ...lastMessage,
                            content,
                            ...(toolAgentSteps && { toolAgentSteps })
                        };
                    }
                    
                    return {
                        ...conv,
                        messages,
                        updatedAt: new Date().toISOString()
                    };
                })
            }));
        },
        
        // Update message by ID
        updateMessage: (conversationId, messageId, updates) => {
            update(state => ({
                ...state,
                conversations: state.conversations.map(conv => {
                    if (conv.id !== conversationId) return conv;
                    
                    return {
                        ...conv,
                        messages: conv.messages.map(msg =>
                            msg.id === messageId
                                ? { ...msg, ...updates }
                                : msg
                        ),
                        updatedAt: new Date().toISOString()
                    };
                })
            }));
        },
        
        // Delete message
        deleteMessage: (conversationId, messageId) => {
            update(state => ({
                ...state,
                conversations: state.conversations.map(conv => {
                    if (conv.id !== conversationId) return conv;
                    
                    return {
                        ...conv,
                        messages: conv.messages.filter(msg => msg.id !== messageId),
                        updatedAt: new Date().toISOString()
                    };
                })
            }));
        },
        
        // Clear all messages in a conversation
        clearMessages: (conversationId) => {
            update(state => ({
                ...state,
                conversations: state.conversations.map(conv => 
                    conv.id === conversationId
                        ? { 
                            ...conv, 
                            messages: [],
                            updatedAt: new Date().toISOString()
                        }
                        : conv
                )
            }));
        },
        
        // Set loading state
        setLoading: (isLoading) => {
            update(state => ({
                ...state,
                isLoading
            }));
        },
        
        // Set error state
        setError: (error) => {
            update(state => ({
                ...state,
                error: error ? (typeof error === 'string' ? error : error.message) : null
            }));
        },
        
        // Clear error
        clearError: () => {
            update(state => ({
                ...state,
                error: null
            }));
        },
        
        // Clear all data
        clearAll: () => {
            set(initialConversationState);
            if (typeof window !== 'undefined') {
                localStorage.removeItem(CONVERSATIONS_STORAGE_KEY);
            }
        },
        
        // Export conversations as JSON
        export: () => {
            const state = get(conversationStore);
            return JSON.stringify(state.conversations, null, 2);
        },
        
        // Import conversations from JSON
        import: (jsonString) => {
            try {
                const imported = JSON.parse(jsonString);
                if (Array.isArray(imported)) {
                    update(state => ({
                        ...state,
                        conversations: [...imported, ...state.conversations]
                    }));
                    return true;
                }
                return false;
            } catch (error) {
                console.error('Failed to import conversations:', error);
                return false;
            }
        },
        
        // Search conversations
        search: (query) => {
            const state = get(conversationStore);
            const lowerQuery = query.toLowerCase();
            
            return state.conversations.filter(conv => {
                if (conv.title.toLowerCase().includes(lowerQuery)) return true;
                return conv.messages.some(msg => 
                    msg.content.toLowerCase().includes(lowerQuery)
                );
            });
        },
        
        // Get conversation by ID
        getById: (id) => {
            const state = get(conversationStore);
            return state.conversations.find(conv => conv.id === id);
        },
        
        // Get current conversation
        getCurrent: () => {
            const state = get(conversationStore);
            if (!state.currentId) return null;
            return state.conversations.find(conv => conv.id === state.currentId);
        },
        
        // Sort conversations by date (newest first)
        sortByDate: (ascending = false) => {
            update(state => ({
                ...state,
                conversations: [...state.conversations].sort((a, b) => {
                    const dateA = new Date(a.updatedAt);
                    const dateB = new Date(b.updatedAt);
                    return ascending ? dateA - dateB : dateB - dateA;
                })
            }));
        }
    };
}

// ==================== SIDEBAR STORE ====================

function createSidebarStore() {
    const { subscribe, set, update } = writable(
        loadFromStorage(SIDEBAR_STORAGE_KEY, initialSidebarState)
    );
    
    // Auto-save on any update
    subscribe(state => {
        saveToStorage(SIDEBAR_STORAGE_KEY, state);
    });
    
    return {
        subscribe,
        
        // Toggle expanded state
        toggleExpanded: () => {
            update(state => ({
                ...state,
                expanded: !state.expanded
            }));
        },
        
        // Set expanded state
        setExpanded: (expanded) => {
            update(state => ({
                ...state,
                expanded
            }));
        },
        
        // Toggle visibility
        toggleVisible: () => {
            update(state => ({
                ...state,
                visible: !state.visible
            }));
        },
        
        // Set visibility
        setVisible: (visible) => {
            update(state => ({
                ...state,
                visible
            }));
        },
        
        // Set current view
        setView: (view) => {
            update(state => ({
                ...state,
                currentView: view
            }));
        },
        
        // Toggle view and expand if needed
        toggleView: (view) => {
            update(state => {
                if (!state.expanded) {
                    // If collapsed, expand and switch to view
                    return {
                        ...state,
                        expanded: true,
                        currentView: view
                    };
                } else if (state.currentView === view) {
                    // If same view, collapse
                    return {
                        ...state,
                        expanded: false
                    };
                } else {
                    // If different view, just switch
                    return {
                        ...state,
                        currentView: view
                    };
                }
            });
        },
        
        // Reset to defaults
        reset: () => {
            set(initialSidebarState);
            if (typeof window !== 'undefined') {
                localStorage.removeItem(SIDEBAR_STORAGE_KEY);
            }
        }
    };
}

// Create and export stores
export const conversationStore = createConversationStore();
export const sidebarStore = createSidebarStore();

// Export convenient actions objects
export const conversationActions = {
    create: conversationStore.create,
    select: conversationStore.select,
    delete: conversationStore.delete,
    updateTitle: conversationStore.updateTitle,
    addMessage: conversationStore.addMessage,
    updateLastMessage: conversationStore.updateLastMessage,
    updateMessage: conversationStore.updateMessage,
    deleteMessage: conversationStore.deleteMessage,
    clearMessages: conversationStore.clearMessages,
    setLoading: conversationStore.setLoading,
    setError: conversationStore.setError,
    clearError: conversationStore.clearError,
    clearAll: conversationStore.clearAll,
    export: conversationStore.export,
    import: conversationStore.import,
    search: conversationStore.search,
    getById: conversationStore.getById,
    getCurrent: conversationStore.getCurrent,
    sortByDate: conversationStore.sortByDate
};

export const sidebarActions = {
    toggleExpanded: sidebarStore.toggleExpanded,
    setExpanded: sidebarStore.setExpanded,
    toggleVisible: sidebarStore.toggleVisible,
    setVisible: sidebarStore.setVisible,
    setView: sidebarStore.setView,
    toggleView: sidebarStore.toggleView,
    reset: sidebarStore.reset
};

// Utility functions for working with conversations
export const conversationUtils = {
    // Format date for display
    formatDate: (dateString) => {
        const date = new Date(dateString);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);
        
        if (diffMins < 1) return 'Just now';
        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffHours < 24) return `${diffHours}h ago`;
        if (diffDays < 7) return `${diffDays}d ago`;
        
        return date.toLocaleDateString();
    },
    
    // Get message count
    getMessageCount: (conversation) => {
        return conversation.messages.length;
    },
    
    // Get conversation preview (first user message)
    getPreview: (conversation) => {
        const firstUserMessage = conversation.messages.find(m => m.role === 'user');
        if (!firstUserMessage) return 'Empty conversation';
        
        const preview = firstUserMessage.content;
        return preview.length > 100 ? preview.substring(0, 97) + '...' : preview;
    },
    
    // Check if conversation is empty
    isEmpty: (conversation) => {
        return !conversation.messages || conversation.messages.length === 0;
    },
    
    // Get total token count estimate (rough)
    estimateTokens: (conversation) => {
        const text = conversation.messages.map(m => m.content).join(' ');
        // Rough estimate: ~4 characters per token
        return Math.ceil(text.length / 4);
    }
};