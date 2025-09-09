# Rhea AI Chat - Frontend Integration

This frontend now integrates with the FastAPI backend to provide a complete AI chat experience with Ollama models.

## Features Implemented

### ✅ Real API Integration
- **Connection Status**: Shows real-time connection to FastAPI server
- **Model Management**: Lists, selects, and manages actual Ollama models
- **Chat Functionality**: Real conversations with selected AI models
- **Tool Integration**: Function calling with available tools
- **Thinking Mode**: GPT-OSS enhanced reasoning support

### ✅ Sidebar Enhancements
- **Chat History**: Real conversation management and persistence
- **Model Selection**: Browse and select from available models
- **Settings Panel**: Connection status, model parameters, system messages
- **Functions Panel**: Tool selection and thinking mode configuration

### ✅ Chat Window Updates
- **Real Conversations**: Actual AI responses from selected models
- **Connection Warnings**: Clear feedback when servers are offline
- **Error Handling**: Graceful error display and recovery
- **Status Indicators**: Real-time feedback on generation status

## Setup Instructions

### 1. Start the Backend Services

First, ensure both Ollama and the FastAPI server are running:

```bash
# Terminal 1: Start Ollama (if not already running)
ollama serve

# Terminal 2: Start FastAPI server
cd backend
./start_server.sh --dev
# or manually:
# python ollama_fastapi.py --reload
```

### 2. Start the Frontend

```bash
# In the frontend directory
npm install  # if not already done
npm run dev
```

### 3. Initial Setup

1. **Check Connection**: The sidebar will show connection status
2. **Pull Models**: If no models are available, pull some:
   ```bash
   ollama pull llama3.2:3b
   ollama pull mistral:7b
   ```
3. **Select Model**: Use the Models panel in the sidebar
4. **Configure Tools**: Enable desired tools in the Functions panel

## API Configuration

The frontend is configured to connect to:
- **FastAPI Server**: `http://localhost:8000`
- **Ollama Server**: `http://localhost:11434` (via FastAPI)

You can modify these URLs in `/src/lib/api.js` if needed.

## Available Features

### Chat Management
- Create new conversations
- View conversation history
- Delete conversations
- Auto-generated titles

### Model Configuration
- List available models
- Select active model
- View model details (parameters, quantization, etc.)
- Model loading/unloading

### Advanced Settings
- Adjust model parameters (temperature, context size, etc.)
- Custom system messages
- System message presets
- Connection monitoring

### Function Calling
- Enable/disable available tools
- Tool status indicators
- Real-time tool selection

### GPT-OSS Features
- Thinking mode toggle
- Reasoning level selection (low, medium, high)
- Enhanced reasoning for compatible models

## Troubleshooting

### Connection Issues
1. **Check Backend Status**: Ensure FastAPI server is running on port 8000
2. **Check Ollama**: Ensure Ollama server is running on port 11434
3. **Network Access**: Verify no firewall blocking the ports

### No Models Available
1. **Pull Models**: Use `ollama pull <model-name>` to download models
2. **Refresh**: Use the refresh button or reload the page
3. **Check Ollama**: Verify models with `ollama list`

### Chat Not Working
1. **Select Model**: Ensure a model is selected in the Models panel
2. **Check Connection**: Verify green connection status
3. **View Errors**: Check browser console for detailed error messages

## Development

### Adding New Features

1. **API Functions**: Add new endpoints to `/src/lib/api.js`
2. **Store Actions**: Extend actions in `/src/lib/stores/ollama.js`
3. **UI Components**: Update sidebar and chat components as needed

### Testing

- Use the test script: `python backend/test_fastapi.py`
- Monitor browser developer tools for API calls
- Check FastAPI docs at: `http://localhost:8000/docs`

## File Structure

```
frontend/src/
├── lib/
│   ├── api.js              # FastAPI client functions
│   ├── stores/
│   │   ├── ollama.js       # Main store with API integration
│   │   ├── ui.js           # UI state management
│   │   └── theme.js        # Theme management
│   └── components/
│       ├── Sidebar.svelte  # Enhanced sidebar with real data
│       ├── ChatWindow.svelte # Real chat functionality
│       └── Navbar.svelte   # Navigation bar
└── routes/
    └── +page.svelte        # Main application page
```

## Next Steps

- [ ] Implement streaming responses
- [ ] Add conversation export/import
- [ ] Enhanced error recovery
- [ ] Model downloading from UI
- [ ] Advanced tool configuration
- [ ] Conversation search and filtering

The system is now fully integrated and ready for production use! 🚀
