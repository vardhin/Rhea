import { writable } from 'svelte/store';
import { browser } from '$app/environment';

const defaultTheme = {
    currentTheme: 'dark',
    colors: {
        // Primary colors
        '--bg-primary': '#1a1a1a',
        '--bg-secondary': '#2d2d2d',
        '--bg-tertiary': '#404040',
        
        // Text colors
        '--text-primary': '#ffffff',
        '--text-secondary': '#b3b3b3',
        '--text-muted': '#666666',
        
        // Accent colors
        '--accent-primary': '#4f46e5',
        '--accent-secondary': '#7c3aed',
        '--accent-success': '#10b981',
        '--accent-warning': '#f59e0b',
        '--accent-error': '#ef4444',
        
        // Border colors
        '--border-primary': '#404040',
        '--border-secondary': '#525252',
        
        // Chat specific
        '--chat-user-bg': '#4f46e5',
        '--chat-assistant-bg': '#2d2d2d',
        '--chat-system-bg': '#1f2937'
    }
};

function createThemeStore() {
    const { subscribe, set, update } = writable(defaultTheme);

    return {
        subscribe,
        setTheme: (theme) => update(state => ({ ...state, currentTheme: theme })),
        updateColors: (colors) => update(state => ({ 
            ...state, 
            colors: { ...state.colors, ...colors }
        })),
        reset: () => set(defaultTheme),
        loadFromStorage: () => {
            if (browser) {
                const stored = localStorage.getItem('rhea-theme');
                if (stored) {
                    set(JSON.parse(stored));
                }
            }
        },
        saveToStorage: (theme) => {
            if (browser) {
                localStorage.setItem('rhea-theme', JSON.stringify(theme));
            }
        }
    };
}

export const themeStore = createThemeStore();