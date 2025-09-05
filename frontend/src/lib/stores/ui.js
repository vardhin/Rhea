import { writable } from 'svelte/store';

export const sidebarStore = writable({
    expanded: false,
    currentView: 'chat', // chat, settings, models, functions
    width: 320
});

export const chatStore = writable({
    conversations: [],
    currentConversationId: null,
    isGenerating: false,
    showQuickActions: true
});

export const modalStore = writable({
    isOpen: false,
    type: null, // 'confirm', 'info', 'error'
    title: '',
    message: '',
    onConfirm: null
});