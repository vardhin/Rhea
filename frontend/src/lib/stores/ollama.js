import { writable } from 'svelte/store';

export const ollamaStore = writable({
    isConnected: false,
    serverUrl: 'http://localhost:11434',
    models: [],
    selectedModel: null,
    modelInfo: null,
    parameters: {
        temperature: 0.7,
        num_ctx: 4096,
        top_k: 40,
        top_p: 0.9,
        repeat_penalty: 1.1
    },
    systemMessage: 'You are a helpful AI assistant.',
    systemPresets: [],
    tools: {
        available: [],
        selected: [],
        enabled: true
    },
    thinkingMode: {
        enabled: false,
        level: 'medium'
    }
});

export const conversationStore = writable({
    conversations: [],
    currentId: null
});