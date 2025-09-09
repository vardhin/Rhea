import { writable, derived } from 'svelte/store';
import { models, config, parameters, tools, thinking, health } from '$lib/api.js';

// Local Storage utilities
const storage = {
    get(key, defaultValue = null) {
        if (typeof window === 'undefined') return defaultValue;
        try {
            const item = localStorage.getItem(key);
            return item ? JSON.parse(item) : defaultValue;
        } catch (error) {
            console.error('Failed to parse localStorage item:', key, error);
            return defaultValue;
        }
    },
    
    set(key, value) {
        if (typeof window === 'undefined') return;
        try {
            localStorage.setItem(key, JSON.stringify(value));
        } catch (error) {
            console.error('Failed to save to localStorage:', key, error);
        }
    },
    
    remove(key) {
        if (typeof window === 'undefined') return;
        localStorage.removeItem(key);
    }
};

// Sidebar store
const sidebarInitialState = {
    visible: storage.get('sidebar_visible', true),
    expanded: storage.get('sidebar_expanded', false),
    currentView: storage.get('sidebar_current_view', 'chat')
};

const sidebarStore = writable(sidebarInitialState);

// Save sidebar state to localStorage
sidebarStore.subscribe(state => {
    storage.set('sidebar_visible', state.visible);
    storage.set('sidebar_expanded', state.expanded);
    storage.set('sidebar_current_view', state.currentView);
});

// Conversation store
const conversationInitialState = {
    conversations: storage.get('conversations', []),
    currentId: storage.get('current_conversation_id', null),
    isLoading: false,
    error: null
};

const conversationStore = writable(conversationInitialState);

// Save conversations to localStorage
conversationStore.subscribe(state => {
    storage.set('conversations', state.conversations);
    storage.set('current_conversation_id', state.currentId);
});

// Conversation actions
export const conversationActions = {
    async create(title = 'New Chat', model = null) {
        const newConversation = {
            id: Date.now().toString() + Math.random().toString(36).substr(2, 9),
            title,
            model: model || null,
            messages: [],
            timestamp: new Date().toISOString(),
            lastModified: new Date().toISOString(),
            systemMessage: storage.get('system_message', '')
        };
        
        conversationStore.update(state => ({
            ...state,
            conversations: [newConversation, ...state.conversations],
            currentId: newConversation.id,
            error: null
        }));
        
        return newConversation.id;
    },
    
    // Alias for backward compatibility
    async createConversation(title = 'New Chat', model = null) {
        return await this.create(title, model);
    },
    
    async select(conversationId) {
        conversationStore.update(state => ({
            ...state,
            currentId: conversationId
        }));
    },
    
    async delete(conversationId) {
        conversationStore.update(state => ({
            ...state,
            conversations: state.conversations.filter(conv => conv.id !== conversationId),
            currentId: state.currentId === conversationId ? null : state.currentId
        }));
    },
    
    async updateTitle(conversationId, title) {
        conversationStore.update(state => ({
            ...state,
            conversations: state.conversations.map(conv => 
                conv.id === conversationId 
                    ? { ...conv, title, lastModified: new Date().toISOString() }
                    : conv
            )
        }));
    },
    
    async updateConversationTitle(conversationId, title) {
        return await this.updateTitle(conversationId, title);
    },
    
    async addMessage(conversationId, message) {
        conversationStore.update(state => ({
            ...state,
            conversations: state.conversations.map(conv => 
                conv.id === conversationId 
                    ? { 
                        ...conv, 
                        messages: [...conv.messages, message],
                        lastModified: new Date().toISOString()
                    }
                    : conv
            )
        }));
    },
    
    async updateLastMessage(conversationId, content) {
        conversationStore.update(state => ({
            ...state,
            conversations: state.conversations.map(conv => 
                conv.id === conversationId 
                    ? { 
                        ...conv, 
                        messages: conv.messages.map((msg, index) => 
                            index === conv.messages.length - 1 
                                ? { ...msg, content }
                                : msg
                        ),
                        lastModified: new Date().toISOString()
                    }
                    : conv
            )
        }));
    },
    
    async updateModel(conversationId, model) {
        conversationStore.update(state => ({
            ...state,
            conversations: state.conversations.map(conv => 
                conv.id === conversationId 
                    ? { ...conv, model, lastModified: new Date().toISOString() }
                    : conv
            )
        }));
    },
    
    async clearAll() {
        conversationStore.update(state => ({
            ...state,
            conversations: [],
            currentId: null,
            error: null
        }));
    },
    
    // Loading state management
    setLoading(loading) {
        conversationStore.update(state => ({
            ...state,
            isLoading: loading
        }));
    },
    
    // Error management
    setError(error) {
        conversationStore.update(state => ({
            ...state,
            error: error ? error.message || error : null
        }));
    },
    
    clearError() {
        conversationStore.update(state => ({
            ...state,
            error: null
        }));
    },
    
    getCurrentConversation() {
        const state = conversationStore;
        return derived(state, $state => 
            $state.conversations.find(conv => conv.id === $state.currentId) || null
        );
    },
    
    // Message management
    async deleteMessage(conversationId, messageId) {
        conversationStore.update(state => ({
            ...state,
            conversations: state.conversations.map(conv => 
                conv.id === conversationId 
                    ? { 
                        ...conv, 
                        messages: conv.messages.filter(msg => msg.id !== messageId),
                        lastModified: new Date().toISOString()
                    }
                    : conv
            )
        }));
    },
    
    async editMessage(conversationId, messageId, newContent) {
        conversationStore.update(state => ({
            ...state,
            conversations: state.conversations.map(conv => 
                conv.id === conversationId 
                    ? { 
                        ...conv, 
                        messages: conv.messages.map(msg => 
                            msg.id === messageId 
                                ? { ...msg, content: newContent, edited: true }
                                : msg
                        ),
                        lastModified: new Date().toISOString()
                    }
                    : conv
            )
        }));
    },
    
    // Conversation management helpers
    async duplicateConversation(conversationId) {
        const state = conversationStore;
        const conversation = state.conversations.find(conv => conv.id === conversationId);
        if (conversation) {
            const newConversation = {
                ...conversation,
                id: Date.now().toString() + Math.random().toString(36).substr(2, 9),
                title: `${conversation.title} (Copy)`,
                timestamp: new Date().toISOString(),
                lastModified: new Date().toISOString()
            };
            
            conversationStore.update(state => ({
                ...state,
                conversations: [newConversation, ...state.conversations],
                currentId: newConversation.id
            }));
            
            return newConversation.id;
        }
        return null;
    },
    
    async exportConversation(conversationId) {
        const state = conversationStore;
        const conversation = state.conversations.find(conv => conv.id === conversationId);
        if (conversation) {
            const exportData = {
                ...conversation,
                exportDate: new Date().toISOString(),
                version: '1.0.0'
            };
            return JSON.stringify(exportData, null, 2);
        }
        return null;
    },
    
    async importConversation(conversationData) {
        try {
            const data = typeof conversationData === 'string' 
                ? JSON.parse(conversationData) 
                : conversationData;
            
            const importedConversation = {
                ...data,
                id: Date.now().toString() + Math.random().toString(36).substr(2, 9),
                timestamp: new Date().toISOString(),
                lastModified: new Date().toISOString(),
                title: `${data.title} (Imported)`
            };
            
            conversationStore.update(state => ({
                ...state,
                conversations: [importedConversation, ...state.conversations],
                currentId: importedConversation.id
            }));
            
            return importedConversation.id;
        } catch (error) {
            console.error('Failed to import conversation:', error);
            throw new Error('Invalid conversation data format');
        }
    },
    
    // Search and filtering
    searchConversations(query) {
        const state = conversationStore;
        return derived(state, $state => {
            if (!query.trim()) return $state.conversations;
            
            return $state.conversations.filter(conv => 
                conv.title.toLowerCase().includes(query.toLowerCase()) ||
                conv.messages.some(msg => 
                    msg.content.toLowerCase().includes(query.toLowerCase())
                )
            );
        });
    },
    
    getConversationsByModel(modelName) {
        const state = conversationStore;
        return derived(state, $state => 
            $state.conversations.filter(conv => conv.model === modelName)
        );
    },
    
    getRecentConversations(limit = 10) {
        const state = conversationStore;
        return derived(state, $state => 
            $state.conversations
                .sort((a, b) => new Date(b.lastModified) - new Date(a.lastModified))
                .slice(0, limit)
        );
    }
};

// Initial state with localStorage persistence
const initialState = {
    // Connection state
    isConnected: false,
    isLoading: false,
    error: null,
    serverUrl: storage.get('server_url', 'http://localhost:8000'),
    ollamaUrl: storage.get('ollama_url', 'http://localhost:11434'),
    
    // Models
    models: [],
    selectedModel: storage.get('selected_model', null),
    modelInfo: null,
    modelCapabilities: null,
    
    // Parameters (persisted in localStorage) - CLEANED UP
    parameters: {
        temperature: 0.7,
        top_p: 0.9,
        top_k: 40,
        repeat_penalty: 1.1,
        seed: -1,
        num_ctx: 2048,
        num_batch: 512,
        num_gqa: 1,
        num_gpu: 1,
        main_gpu: 0,
        low_vram: false,
        f16_kv: true,
        logits_all: false,
        vocab_only: false,
        use_mmap: true,
        use_mlock: false,
        num_thread: 0,
        // Remove invalid parameters that cause Ollama warnings:
        // tfs_z, mirostat_tau, mirostat_eta, mirostat
        ...storage.get('model_parameters', {})
    },
    
    // Tools (persisted in localStorage)
    tools: {
        available: {},
        selected: storage.get('selected_tools', []),
        enabled: storage.get('tools_enabled', true)
    },
    
    // Thinking mode (persisted in localStorage)
    thinkingMode: {
        enabled: storage.get('thinking_mode_enabled', false),
        level: storage.get('thinking_mode_level', 1),
        levels: [1, 2, 3]
    },
    
    // System message (persisted in localStorage)
    systemMessage: storage.get('system_message', ''),
    selectedSystemPreset: storage.get('selected_system_preset', ''),
    systemPresets: storage.get('system_presets', [
        {
            name: 'Default Assistant',
            message: 'You are a helpful AI assistant. Answer questions clearly and concisely.'
        },
        {
            name: 'Creative Writer',
            message: 'You are a creative writing assistant. Help with storytelling, character development, and creative expression.'
        },
        {
            name: 'Code Helper',
            message: 'You are a programming assistant. Help with code, debugging, and technical explanations. Be precise and provide working examples.'
        },
        {
            name: 'Research Assistant',
            message: 'You are a research assistant. For current events or recent information, acknowledge when you need up-to-date data and explain your limitations with training data. Provide thorough, well-researched answers based on your knowledge.'
        }
    ]),
    
    // Settings (persisted in localStorage)
    settings: {
        theme: storage.get('theme', 'dark'),
        autoSave: storage.get('auto_save', true),
        streamingEnabled: storage.get('streaming_enabled', true),
        showTimestamps: storage.get('show_timestamps', true),
        compactMode: storage.get('compact_mode', false),
        ...storage.get('app_settings', {})
    },
    
    // Constants
    constants: {
        contextSizes: {
            1024: '1K tokens',
            2048: '2K tokens',
            4096: '4K tokens',
            8192: '8K tokens',
            16384: '16K tokens',
            32768: '32K tokens',
            65536: '64K tokens',
            131072: '128K tokens'
        },
        temperatureRange: { min: 0, max: 2, step: 0.1 },
        topPRange: { min: 0, max: 1, step: 0.05 }
    }
};

// Create the store
const store = writable(initialState);

// Save important state changes to localStorage
store.subscribe(state => {
    storage.set('selected_model', state.selectedModel);
    storage.set('model_parameters', state.parameters);
    storage.set('selected_tools', state.tools.selected);
    storage.set('tools_enabled', state.tools.enabled);
    storage.set('thinking_mode_enabled', state.thinkingMode.enabled);
    storage.set('thinking_mode_level', state.thinkingMode.level);
    storage.set('system_message', state.systemMessage);
    storage.set('selected_system_preset', state.selectedSystemPreset);
    storage.set('system_presets', state.systemPresets);
    storage.set('app_settings', state.settings);
    storage.set('server_url', state.serverUrl);
    storage.set('ollama_url', state.ollamaUrl);
});

// Actions
export const ollamaActions = {
    // Connection management
    async checkConnection() {
        store.update(s => ({ ...s, isLoading: true, error: null }));
        
        try {
            const healthData = await health.check();
            
            store.update(s => ({
                ...s,
                isConnected: healthData.status === 'healthy',
                isLoading: false,
                error: null
            }));
            
            // Load initial data if connected
            if (healthData.status === 'healthy') {
                await Promise.all([
                    this.loadModels(),
                    this.loadTools(),
                    this.loadThinkingMode(),
                    this.loadConfig()
                ]);
            }
            
            return healthData.status === 'healthy';
        } catch (error) {
            console.error('Connection check failed:', error);
            store.update(s => ({
                ...s,
                isConnected: false,
                isLoading: false,
                error: error.message
            }));
            return false;
        }
    },
    
    // Server URL management
    async setServerUrl(url) {
        store.update(s => ({ ...s, serverUrl: url }));
        // Reconnect with new URL
        return await this.checkConnection();
    },
    
    async setOllamaUrl(url) {
        store.update(s => ({ ...s, ollamaUrl: url }));
    },
    
    // Models
    async loadModels() {
        try {
            const modelsList = await models.getAll();
            store.update(s => ({
                ...s,
                models: modelsList,
                error: null
            }));
            return modelsList;
        } catch (error) {
            console.error('Failed to load models:', error);
            store.update(s => ({ ...s, error: error.message }));
            throw error;
        }
    },
    
    async selectModel(modelName) {
        store.update(s => ({ ...s, isLoading: true }));
        
        try {
            const [modelInfo, capabilities, defaultParams] = await Promise.all([
                models.getInfo(modelName),
                models.getCapabilities(modelName),
                models.getParameters(modelName)
            ]);
            
            store.update(s => ({
                ...s,
                selectedModel: modelName,
                modelInfo,
                modelCapabilities: capabilities,
                parameters: { ...s.parameters, ...defaultParams },
                isLoading: false,
                error: null
            }));
            
            return { modelInfo, capabilities, defaultParams };
        } catch (error) {
            console.error('Failed to select model:', error);
            store.update(s => ({
                ...s,
                isLoading: false,
                error: error.message
            }));
            throw error;
        }
    },
    
    // Parameters
    async loadParameters(model = null) {
        try {
            const params = await parameters.get(model);
            store.update(s => ({
                ...s,
                parameters: { ...s.parameters, ...params },
                error: null
            }));
            return params;
        } catch (error) {
            console.error('Failed to load parameters:', error);
            // Use local storage values as fallback
            return storage.get('model_parameters', {});
        }
    },
    
    async updateParameters(newParams, model = null) {
        // Filter out invalid parameters before storing
        const validParams = [
            'temperature', 'top_p', 'top_k', 'repeat_penalty', 'seed',
            'num_ctx', 'num_batch', 'num_gqa', 'num_gpu', 'main_gpu',
            'low_vram', 'f16_kv', 'logits_all', 'vocab_only', 'use_mmap',
            'use_mlock', 'num_thread'
        ];

        const filteredParams = Object.keys(newParams)
            .filter(key => validParams.has(key))
            .reduce((obj, key) => {
                obj[key] = newParams[key];
                return obj;
            }, {});
        
        store.update(s => ({
            ...s,
            parameters: { ...s.parameters, ...filteredParams }
        }));
        
        try {
            const updatedParams = await parameters.set(filteredParams, model);
            store.update(s => ({
                ...s,
                parameters: { ...s.parameters, ...updatedParams },
                error: null
            }));
            return updatedParams;
        } catch (error) {
            console.error('Failed to update parameters on server:', error);
            // Parameters are still saved locally via store subscription
            return filteredParams;
        }
    },
    
    // Tools
    async loadTools() {
        try {
            const toolsData = await tools.getAll();
            store.update(s => ({
                ...s,
                tools: {
                    ...s.tools,
                    available: toolsData.available || {},
                    selected: toolsData.selected || []
                },
                error: null
            }));
            return toolsData;
        } catch (error) {
            console.error('Failed to load tools from server:', error);
            // Use local storage values as fallback
            const localTools = storage.get('selected_tools', []);
            store.update(s => ({
                ...s,
                tools: { ...s.tools, selected: localTools }
            }));
            return { available: {}, selected: localTools };
        }
    },

    async selectTools(toolNames) {
        store.update(s => ({
            ...s,
            tools: { ...s.tools, selected: toolNames }
        }));
        
        try {
            const result = await tools.select(toolNames);
            store.update(s => ({
                ...s,
                tools: {
                    ...s.tools,
                    selected: result.selected || toolNames,
                    available: result.available || s.tools.available
                },
                error: null
            }));
            return result;
        } catch (error) {
            console.error('Failed to select tools on server:', error);
            // Tools selection is still saved locally via store subscription
            return { selected: toolNames, available: {} };
        }
    },
    
    // Thinking mode
    async loadThinkingMode() {
        try {
            const thinkingData = await thinking.get();
            store.update(s => ({
                ...s,
                thinkingMode: { ...s.thinkingMode, ...thinkingData },
                error: null
            }));
            return thinkingData;
        } catch (error) {
            console.error('Failed to load thinking mode from server:', error);
            // Use local storage values as fallback
            const localThinking = {
                enabled: storage.get('thinking_mode_enabled', false),
                level: storage.get('thinking_mode_level', 1)
            };
            return localThinking;
        }
    },
    
    async setThinkingMode(enabled, level = 1) {
        store.update(s => ({
            ...s,
            thinkingMode: { ...s.thinkingMode, enabled, level }
        }));
        
        try {
            const result = await thinking.set(enabled, level);
            store.update(s => ({
                ...s,
                thinkingMode: { ...s.thinkingMode, ...result },
                error: null
            }));
            return result;
        } catch (error) {
            console.error('Failed to set thinking mode on server:', error);
            // Thinking mode is still saved locally via store subscription
            return { enabled, level };
        }
    },
    
    // Configuration
    async loadConfig() {
        try {
            const configData = await config.getAll();
            store.update(s => ({
                ...s,
                ...configData,
                error: null
            }));
            return configData;
        } catch (error) {
            console.error('Failed to load config from server:', error);
            // Use local storage values as fallback
            return storage.get('app_settings', {});
        }
    },
    
    // System message
    updateSystemMessage(message) {
        store.update(s => ({
            ...s,
            systemMessage: message
        }));
    },
    
    selectSystemPreset(presetName) {
        store.update(s => {
            const preset = s.systemPresets.find(p => p.name === presetName);
            return {
                ...s,
                systemMessage: preset ? preset.message : s.systemMessage,
                selectedSystemPreset: presetName
            };
        });
    },
    
    addSystemPreset(name, message) {
        store.update(s => ({
            ...s,
            systemPresets: [...s.systemPresets, { name, message }]
        }));
    },
    
    removeSystemPreset(name) {
        store.update(s => ({
            ...s,
            systemPresets: s.systemPresets.filter(p => p.name !== name)
        }));
    },
    
    // Settings management
    updateSetting(key, value) {
        store.update(s => ({
            ...s,
            settings: { ...s.settings, [key]: value }
        }));
    },
    
    updateSettings(newSettings) {
        store.update(s => ({
            ...s,
            settings: { ...s.settings, ...newSettings }
        }));
    },
    
    resetSettings() {
        const defaultSettings = {
            theme: 'dark',
            autoSave: true,
            streamingEnabled: true,
            showTimestamps: true,
            compactMode: false
        };
        
        store.update(s => ({
            ...s,
            settings: defaultSettings
        }));
    },
    
    // Data management
    exportData() {
        const conversations = storage.get('conversations', []);
        const settings = storage.get('app_settings', {});
        const parameters = storage.get('model_parameters', {});
        const systemPresets = storage.get('system_presets', []);
        
        return {
            conversations,
            settings,
            parameters,
            systemPresets,
            exportDate: new Date().toISOString(),
            version: '1.0.0'
        };
    },
    
    importData(data) {
        try {
            if (data.conversations) {
                conversationStore.update(s => ({
                    ...s,
                    conversations: data.conversations
                }));
            }
            
            if (data.settings) {
                this.updateSettings(data.settings);
            }
            
            if (data.parameters) {
                this.updateParameters(data.parameters);
            }
            
            if (data.systemPresets) {
                store.update(s => ({
                    ...s,
                    systemPresets: data.systemPresets
                }));
            }
            
            return true;
        } catch (error) {
            console.error('Failed to import data:', error);
            return false;
        }
    },
    
    clearAllData() {
        // Clear conversations
        conversationActions.clearAll();
        
        // Clear other data
        ['model_parameters', 'selected_tools', 'system_message', 'system_presets', 'app_settings'].forEach(key => {
            storage.remove(key);
        });
        
        // Reset store to initial state
        store.set(initialState);
    },
    
    // Error handling
    clearError() {
        store.update(s => ({ ...s, error: null }));
    }
};

// Export the stores and actions
export const ollamaStore = store;
export { sidebarStore, conversationStore };

// Derived stores
export const isConnected = derived(store, $store => $store.isConnected);
export const selectedModel = derived(store, $store => $store.selectedModel);
export const availableModels = derived(store, $store => $store.models);
export const currentParameters = derived(store, $store => $store.parameters);
export const availableTools = derived(store, $store => $store.tools.available);
export const selectedTools = derived(store, $store => $store.tools.selected);

// Sidebar derived stores
export const sidebarVisible = derived(sidebarStore, $sidebar => $sidebar.visible);
export const sidebarExpanded = derived(sidebarStore, $sidebar => $sidebar.expanded);
export const currentSidebarView = derived(sidebarStore, $sidebar => $sidebar.currentView);

// Conversation derived stores
export const currentConversation = derived(conversationStore, $conversations => 
    $conversations.conversations.find(conv => conv.id === $conversations.currentId) || null
);
export const conversationList = derived(conversationStore, $conversations => $conversations.conversations);
export const conversationCount = derived(conversationStore, $conversations => $conversations.conversations.length);

// Enhanced system message with stronger tool instructions
function getSystemMessageWithToolInstructions() {
    return currentConversation?.systemMessage || $ollamaStore.systemMessage || 'You are a helpful AI assistant.';
}