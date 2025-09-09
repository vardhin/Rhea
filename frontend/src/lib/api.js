const API_BASE_URL = 'http://localhost:8000';

class APIError extends Error {
    constructor(message, status, data = null) {
        super(message);
        this.name = 'APIError';
        this.status = status;
        this.data = data;
    }
}

async function fetchAPI(endpoint, options = {}) {
    try {
        const response = await fetch(`${API_BASE_URL}${endpoint}`, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => null);
            throw new APIError(
                errorData?.detail || `HTTP ${response.status}: ${response.statusText}`,
                response.status,
                errorData
            );
        }
        
        return await response.json();
    } catch (error) {
        if (error instanceof APIError) throw error;
        throw new APIError(`Network error: ${error.message}`, 0);
    }
}

// Models API
export const models = {
    async getAll() {
        try {
            const data = await fetchAPI('/models');
            return data.models || [];
        } catch (error) {
            console.error('Failed to fetch models:', error);
            throw error;
        }
    },
    
    async getInfo(modelName) {
        try {
            const encodedName = encodeURIComponent(modelName);
            const data = await fetchAPI(`/models/${encodedName}/info`);
            return data.model_info;
        } catch (error) {
            console.error(`Failed to get info for model ${modelName}:`, error);
            throw error;
        }
    },
    
    async getCapabilities(modelName) {
        try {
            const encodedName = encodeURIComponent(modelName);
            const data = await fetchAPI(`/models/${encodedName}/capabilities`);
            return data.capabilities;
        } catch (error) {
            console.error(`Failed to get capabilities for model ${modelName}:`, error);
            throw error;
        }
    },
    
    async getParameters(modelName) {
        try {
            const encodedName = encodeURIComponent(modelName);
            const data = await fetchAPI(`/models/${encodedName}/parameters`);
            return data.parameters;
        } catch (error) {
            console.error(`Failed to get parameters for model ${modelName}:`, error);
            throw error;
        }
    }
};

// Chat API
export const chat = {
    async send(messages, options = {}) {
        try {
            const {
                model,
                systemMessage = '',
                useSelectedTools = false,
                thinkingMode = false,
                thinkingLevel = 1
            } = options;

            // Get the last message content for the API
            const lastMessage = Array.isArray(messages) && messages.length > 0 
                ? messages[messages.length - 1] 
                : null;

            if (!lastMessage) {
                throw new Error('No messages provided');
            }

            const requestBody = {
                model: model || 'llama2',
                message: lastMessage.content || '',
                stream: false,
                use_tools: useSelectedTools,
                system_message: systemMessage,
                thinking_mode: thinkingMode,
                thinking_level: thinkingLevel
            };

            console.log('Sending chat request:', requestBody);

            const response = await fetch(`${API_BASE_URL}/chat`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(requestBody)
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => null);
                throw new APIError(
                    errorData?.detail || `HTTP error! status: ${response.status}`,
                    response.status,
                    errorData
                );
            }

            const data = await response.json();
            return { message: { content: data.response || '' } };
        } catch (error) {
            console.error('Chat send error:', error);
            throw error;
        }
    }
};

// Streaming chat - single implementation
export const createStreamingChat = async (messages, options = {}) => {
    const {
        model,
        systemMessage = '',
        useSelectedTools = false,
        thinkingMode = false,
        thinkingLevel = 1
    } = options;

    if (!Array.isArray(messages) || messages.length === 0) {
        throw new Error('No messages provided');
    }

    // Send ALL messages, not just the last one
    const requestBody = {
        model: model || 'llama2',
        messages: messages, // Send full conversation history
        message: messages[messages.length - 1]?.content || '', // Keep for backward compatibility
        stream: true,
        use_tools: useSelectedTools,
        system_message: systemMessage,
        thinking_mode: thinkingMode,
        thinking_level: thinkingLevel
    };

    console.log('Sending streaming chat request:', requestBody);

    const response = await fetch(`${API_BASE_URL}/chat`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody)
    });

    if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        throw new APIError(
            errorData?.detail || `HTTP error! status: ${response.status}`,
            response.status,
            errorData
        );
    }

    return {
        async *getIterator() {
            const reader = response.body?.getReader();
            if (!reader) throw new Error('No reader available');

            const decoder = new TextDecoder();
            let buffer = '';

            try {
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;

                    buffer += decoder.decode(value, { stream: true });
                    const lines = buffer.split('\n');
                    buffer = lines.pop() || '';

                    for (const line of lines) {
                        if (line.trim() === '') continue;
                        
                        if (line.startsWith('data: ')) {
                            try {
                                const jsonData = line.slice(6).trim();
                                if (jsonData === '') continue;
                                
                                const data = JSON.parse(jsonData);
                                
                                // Handle content chunks
                                if (data.chunk) {
                                    yield { 
                                        message: { 
                                            content: data.chunk,
                                            role: 'assistant'
                                        } 
                                    };
                                }
                                
                                // Handle tool calls
                                if (data.tool_call) {
                                    yield { 
                                        tool_call: data.tool_call
                                    };
                                }
                                
                                // Handle debug info
                                if (data.debug) {
                                    yield {
                                        debug: data.debug
                                    };
                                }
                                
                                // Handle errors
                                if (data.error) {
                                    throw new Error(data.error);
                                }
                                
                            } catch (e) {
                                console.warn('Failed to parse streaming data:', line, e);
                            }
                        }
                    }
                }
            } finally {
                reader.releaseLock();
            }
        },
        
        async close() {
            try {
                await response.body?.cancel();
            } catch (e) {
                console.warn('Error closing stream:', e);
            }
        }
    };
};

// Configuration API
export const config = {
    async getAll() {
        try {
            const data = await fetchAPI('/config');
            return data.config || {};
        } catch (error) {
            console.error('Failed to fetch config:', error);
            throw error;
        }
    },
    
    async getServerInfo() {
        try {
            const data = await fetchAPI('/server/info');
            return data.server || {};
        } catch (error) {
            console.error('Failed to fetch server info:', error);
            throw error;
        }
    },
    
    async setServerUrl(url) {
        try {
            const data = await fetchAPI('/server/url', {
                method: 'POST',
                body: JSON.stringify({ url })
            });
            return data;
        } catch (error) {
            console.error('Failed to set server URL:', error);
            throw error;
        }
    }
};

// Parameters API
export const parameters = {
    async get(model = null) {
        try {
            const params = new URLSearchParams();
            if (model) params.append('model', model);
            
            const data = await fetchAPI(`/parameters?${params}`);
            return data.parameters || {};
        } catch (error) {
            console.error('Failed to get parameters:', error);
            throw error;
        }
    },
    
    async set(parameters, model = null) {
        try {
            const data = await fetchAPI('/parameters', {
                method: 'POST',
                body: JSON.stringify({ parameters, model })
            });
            return data.parameters || {};
        } catch (error) {
            console.error('Failed to set parameters:', error);
            throw error;
        }
    }
};

// Tools API
export const tools = {
    async getAll() {
        try {
            const response = await fetch(`${API_BASE_URL}/tools`);
            if (!response.ok) {
                const errorData = await response.json().catch(() => null);
                throw new APIError(
                    errorData?.detail || `HTTP error! status: ${response.status}`,
                    response.status,
                    errorData
                );
            }
            const data = await response.json();
            return {
                available: data.available || {},
                selected: data.selected || []
            };
        } catch (error) {
            console.error('Failed to fetch tools:', error);
            throw error;
        }
    },

    async select(toolNames) {
        try {
            const response = await fetch(`${API_BASE_URL}/tools/select`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ tools: toolNames || [] })
            });
            
            if (!response.ok) {
                const errorData = await response.json().catch(() => null);
                throw new APIError(
                    errorData?.detail || `HTTP error! status: ${response.status}`,
                    response.status,
                    errorData
                );
            }
            
            const data = await response.json();
            return {
                selected: data.selected || [],
                available: data.available || {}
            };
        } catch (error) {
            console.error('Failed to select tools:', error);
            throw error;
        }
    }
};

// Thinking mode API
export const thinking = {
    async get() {
        try {
            const response = await fetch(`${API_BASE_URL}/thinking`);
            if (!response.ok) {
                const errorData = await response.json().catch(() => null);
                throw new APIError(
                    errorData?.detail || `HTTP error! status: ${response.status}`,
                    response.status,
                    errorData
                );
            }
            const data = await response.json();
            return data.thinking_mode || { enabled: false, level: 1 };
        } catch (error) {
            console.error('Failed to fetch thinking mode:', error);
            throw error;
        }
    },

    async set(enabled, level = 1) {
        try {
            const response = await fetch(`${API_BASE_URL}/thinking`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ enabled: !!enabled, level: Number(level) || 1 })
            });
            
            if (!response.ok) {
                const errorData = await response.json().catch(() => null);
                throw new APIError(
                    errorData?.detail || `HTTP error! status: ${response.status}`,
                    response.status,
                    errorData
                );
            }
            
            const data = await response.json();
            return data.thinking_mode || { enabled, level };
        } catch (error) {
            console.error('Failed to set thinking mode:', error);
            throw error;
        }
    }
};

// Health check
export const health = {
    async check() {
        try {
            const data = await fetchAPI('/health');
            return data;
        } catch (error) {
            console.error('Health check failed:', error);
            return { status: 'unhealthy', error: error.message };
        }
    }
};

export { APIError };