import { writable } from 'svelte/store';

export const sidebarStore = writable({
    visible: true,    // Controls fade in/out (hamburger menu)
    expanded: false   // Controls expand/contract (sidebar toggle button)
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