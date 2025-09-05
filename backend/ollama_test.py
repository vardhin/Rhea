from ollama_module import OllamaManager, MODEL_PARAMETERS, CONTEXT_SIZES, REASONING_LEVELS, QUANTIZATION_TYPES
import json

class OllamaTestMenu:
    def __init__(self):
        self.manager = OllamaManager()
        self.selected_model = None
        self.available_models = []
        
    def display_main_menu(self):
        print("\n" + "="*60)
        print("OLLAMA MANAGER COMPREHENSIVE TEST MENU")
        print("="*60)
        print("MODEL MANAGEMENT:")
        print("1. List available models")
        print("2. Select a model") 
        print("3. View current model info")
        print("4. Get context information")
        print("5. List running models")
        print("6. Load/Unload models")
        print("")
        print("MODEL CONFIGURATION:")
        print("7. Set model parameters")
        print("8. Create custom model")
        print("9. Copy model")
        print("10. Delete model")
        print("11. Pull model from library")
        print("")
        print("TOOLS MANAGEMENT:")
        print("12. List available tools")
        print("13. Select/manage tools")
        print("14. Add custom tool")
        print("")
        print("CHAT & GENERATION:")
        print("15. Chat with model")
        print("16. Chat with custom options")
        print("17. Generate text")
        print("18. Generate with options")
        print("")
        print("GPT-OSS SPECIFIC:")
        print("19. Configure thinking mode")
        print("20. Set reasoning level")
        print("")
        print("EMBEDDINGS & UTILITIES:")
        print("21. Generate embeddings")
        print("22. Server information")
        print("23. Debug tools")
        print("24. Test all functions")
        print("")
        print("0. Exit")
        print("-"*60)
        
    def list_models(self):
        print("\n=== Available Models ===")
        try:
            models_data = self.manager.list_models()
            self.available_models = models_data.get('models', [])
            
            if not self.available_models:
                print("No models found!")
                return
                
            for i, model in enumerate(self.available_models):
                print(f"{i+1}. {model.get('name', 'Unknown')}")
                if model.get('size'):
                    print(f"   Size: {model.get('size')}")
                if model.get('modified_at'):
                    print(f"   Modified: {model.get('modified_at')}")
                if model.get('details'):
                    details = model.get('details', {})
                    if details.get('family'):
                        print(f"   Family: {details.get('family')}")
                    if details.get('parameter_size'):
                        print(f"   Parameters: {details.get('parameter_size')}")
                print()
        except Exception as e:
            print(f"Error listing models: {e}")
    
    def select_model(self):
        if not self.available_models:
            print("Please list models first (option 1)")
            return
            
        print("\n=== Select Model ===")
        for i, model in enumerate(self.available_models):
            print(f"{i+1}. {model.get('name', 'Unknown')}")
        
        try:
            choice = int(input("\nEnter model number (0 to cancel): "))
            if choice == 0:
                return
            if 1 <= choice <= len(self.available_models):
                model_name = self.available_models[choice-1].get('name', '')
                print(f"Attempting to select: {model_name}")
                if self.manager.select_model(model_name):
                    self.selected_model = model_name
                    print(f"✓ Successfully selected: {model_name}")
                    
                    # Check if it's a GPT-OSS model
                    if 'gpt-oss' in model_name.lower():
                        print("🧠 GPT-OSS model detected - advanced reasoning available")
                    else:
                        print("📝 Standard model selected")
                else:
                    print("✗ Failed to select model")
            else:
                print("Invalid choice")
        except ValueError:
            print("Please enter a valid number")
    
    def view_model_info(self):
        print("\n=== Current Model Info ===")
        if not self.selected_model:
            print("No model selected")
            return
            
        try:
            print(f"Selected model: {self.selected_model}")
            info = self.manager.get_model_info()
            
            print("\n📊 Model Details:")
            details = info.get('details', {})
            for key, value in details.items():
                print(f"  {key}: {value}")
            
            print(f"\n🔧 GPT-OSS features: {'Yes' if 'gpt-oss' in self.selected_model.lower() else 'No'}")
            
            if info.get('modelfile'):
                print(f"\n📄 Modelfile preview: {info['modelfile'][:200]}...")
                
        except Exception as e:
            print(f"Error getting model info: {e}")
    
    def get_context_info(self):
        print("\n=== Context Information ===")
        if not self.selected_model:
            print("No model selected")
            return
            
        try:
            context_info = self.manager.get_context_info()
            print("Context Information:")
            for key, value in context_info.items():
                print(f"  {key}: {value}")
        except Exception as e:
            print(f"Error getting context info: {e}")
    
    def list_running_models(self):
        print("\n=== Running Models ===")
        try:
            running = self.manager.list_running_models()
            models = running.get('models', [])
            
            if not models:
                print("No models currently loaded in memory")
                return
                
            for model in models:
                print(f"🔄 {model.get('name', 'Unknown')}")
                if model.get('size'):
                    print(f"   Memory usage: {model.get('size')}")
                if model.get('expires_at'):
                    print(f"   Expires: {model.get('expires_at')}")
        except Exception as e:
            print(f"Error listing running models: {e}")
    
    def load_unload_models(self):
        print("\n=== Load/Unload Models ===")
        print("1. Load a model into memory")
        print("2. Unload a model from memory")
        print("3. View running models")
        
        choice = input("Choice: ")
        
        if choice == "1":
            model_name = input("Enter model name to load: ")
            print(f"Loading {model_name}...")
            if self.manager.load_model(model_name):
                print("✓ Model loaded successfully")
            else:
                print("✗ Failed to load model")
                
        elif choice == "2":
            model_name = input("Enter model name to unload: ")
            print(f"Unloading {model_name}...")
            if self.manager.unload_model(model_name):
                print("✓ Model unloaded successfully")
            else:
                print("✗ Failed to unload model")
                
        elif choice == "3":
            self.list_running_models()
    
    def set_model_parameters(self):
        print("\n=== Set Model Parameters ===")
        if not self.selected_model:
            print("Please select a model first")
            return
            
        print("Available parameters:")
        for i, (param, desc) in enumerate(MODEL_PARAMETERS.items(), 1):
            print(f"{i:2d}. {param:15s} - {desc}")
        
        print("\nConfigure parameters (press Enter to skip):")
        
        params = {}
        
        # Context window
        ctx = input(f"Context window size {list(CONTEXT_SIZES.keys())}: ")
        if ctx.isdigit():
            params['num_ctx'] = int(ctx)
            
        # Temperature
        temp = input("Temperature (0.0-2.0): ")
        if temp:
            try:
                params['temperature'] = float(temp)
            except ValueError:
                print("Invalid temperature value")
        
        # Other common parameters
        top_k = input("Top-k sampling (e.g., 40): ")
        if top_k.isdigit():
            params['top_k'] = int(top_k)
            
        top_p = input("Top-p sampling (0.0-1.0): ")
        if top_p:
            try:
                params['top_p'] = float(top_p)
            except ValueError:
                print("Invalid top-p value")
        
        if params:
            result = self.manager.set_model_parameters(**params)
            print("✓ Parameters set:", result)
        else:
            print("No parameters configured")
    
    def create_custom_model(self):
        print("\n=== Create Custom Model ===")
        if not self.available_models:
            print("Please list models first")
            return
            
        model_name = input("New model name: ")
        
        print("\nAvailable base models:")
        for i, model in enumerate(self.available_models):
            print(f"{i+1}. {model.get('name')}")
            
        try:
            choice = int(input("Select base model number: "))
            if 1 <= choice <= len(self.available_models):
                base_model = self.available_models[choice-1]['name']
                
                system_prompt = input("System prompt (optional): ")
                
                print("Would you like to set parameters? (y/n): ")
                if input().lower() == 'y':
                    params = {}
                    
                    ctx = input("Context size (optional): ")
                    if ctx.isdigit():
                        params['num_ctx'] = int(ctx)
                        
                    temp = input("Temperature (optional): ")
                    if temp:
                        try:
                            params['temperature'] = float(temp)
                        except ValueError:
                            pass
                    
                    print("Creating custom model...")
                    try:
                        response = self.manager.create_custom_model(
                            model_name=model_name,
                            base_model=base_model,
                            system_prompt=system_prompt if system_prompt else None,
                            **params
                        )
                        print("✓ Custom model creation initiated")
                        # If streaming, show progress
                        if hasattr(response, '__iter__'):
                            for chunk in response:
                                if chunk.get('status'):
                                    print(f"Status: {chunk['status']}")
                    except Exception as e:
                        print(f"Error creating model: {e}")
                else:
                    try:
                        response = self.manager.create_custom_model(
                            model_name=model_name,
                            base_model=base_model,
                            system_prompt=system_prompt if system_prompt else None
                        )
                        print("✓ Custom model creation initiated")
                    except Exception as e:
                        print(f"Error creating model: {e}")
            else:
                print("Invalid choice")
        except ValueError:
            print("Please enter a valid number")
    
    def copy_model(self):
        print("\n=== Copy Model ===")
        if not self.available_models:
            print("Please list models first")
            return
            
        print("Available models:")
        for i, model in enumerate(self.available_models):
            print(f"{i+1}. {model.get('name')}")
            
        try:
            choice = int(input("Select model to copy: "))
            if 1 <= choice <= len(self.available_models):
                source = self.available_models[choice-1]['name']
                destination = input("New model name: ")
                
                if self.manager.copy_model(source, destination):
                    print(f"✓ Successfully copied {source} to {destination}")
                else:
                    print("✗ Failed to copy model")
            else:
                print("Invalid choice")
        except ValueError:
            print("Please enter a valid number")
    
    def delete_model(self):
        print("\n=== Delete Model ===")
        if not self.available_models:
            print("Please list models first")
            return
            
        print("Available models:")
        for i, model in enumerate(self.available_models):
            print(f"{i+1}. {model.get('name')}")
            
        try:
            choice = int(input("Select model to delete: "))
            if 1 <= choice <= len(self.available_models):
                model_name = self.available_models[choice-1]['name']
                
                confirm = input(f"Are you sure you want to delete {model_name}? (yes/no): ")
                if confirm.lower() == 'yes':
                    if self.manager.delete_model(model_name):
                        print(f"✓ Successfully deleted {model_name}")
                        # Remove from local list
                        self.available_models = [m for m in self.available_models if m['name'] != model_name]
                    else:
                        print("✗ Failed to delete model")
                else:
                    print("Delete cancelled")
            else:
                print("Invalid choice")
        except ValueError:
            print("Please enter a valid number")
    
    def pull_model(self):
        print("\n=== Pull Model from Library ===")
        print("Popular models:")
        print("1. llama3.2:3b")
        print("2. llama3.2:1b")
        print("3. mistral:7b")
        print("4. codellama:7b")
        print("5. phi3:3.8b")
        print("6. Custom model name")
        
        choice = input("Choice (or model name): ")
        
        model_map = {
            '1': 'llama3.2:3b',
            '2': 'llama3.2:1b', 
            '3': 'mistral:7b',
            '4': 'codellama:7b',
            '5': 'phi3:3.8b'
        }
        
        if choice in model_map:
            model_name = model_map[choice]
        elif choice == '6':
            model_name = input("Enter model name: ")
        else:
            model_name = choice
            
        print(f"Pulling {model_name}...")
        try:
            response = self.manager.pull_model(model_name, stream=True)
            
            # Show pull progress
            for chunk in response:
                if chunk.get('status'):
                    status = chunk['status']
                    if chunk.get('completed') and chunk.get('total'):
                        completed = chunk['completed']
                        total = chunk['total']
                        percent = (completed / total) * 100
                        print(f"\r{status}: {percent:.1f}%", end='')
                    else:
                        print(f"\r{status}", end='')
                        
            print(f"\n✓ Successfully pulled {model_name}")
            
        except Exception as e:
            print(f"Error pulling model: {e}")
    
    def list_tools(self):
        print("\n=== Available Tools ===")
        try:
            tools = self.manager.get_available_tools()
            for i, (name, tool_def) in enumerate(tools.items(), 1):
                func_info = tool_def.get('function', {})
                print(f"{i}. {name}")
                print(f"   Description: {func_info.get('description', 'No description')}")
                
            selected = self.manager.selected_tools
            if selected:
                selected_names = [tool.get('function', {}).get('name', 'unknown') for tool in selected]
                print(f"\nCurrently selected: {', '.join(selected_names)}")
            else:
                print("\nNo tools currently selected")
        except Exception as e:
            print(f"Error listing tools: {e}")
    
    def manage_tools(self):
        print("\n=== Tool Management ===")
        print("1. Select tools")
        print("2. View selected tools")
        print("3. Clear selected tools")
        print("4. View tool details")
        
        choice = input("Choice: ")
        
        if choice == "1":
            self.select_tools()
        elif choice == "2":
            selected = self.manager.selected_tools
            if selected:
                print("Selected tools:")
                for tool in selected:
                    func_name = tool.get('function', {}).get('name', 'unknown')
                    print(f"  - {func_name}")
            else:
                print("No tools selected")
        elif choice == "3":
            self.manager.selected_tools = []
            print("Cleared all selected tools")
        elif choice == "4":
            self.view_tool_details()
    
    def select_tools(self):
        try:
            available_tools = self.manager.get_available_tools()
            tool_names = list(available_tools.keys())
            
            print("\nAvailable tools:")
            for i, tool_name in enumerate(tool_names, 1):
                tool_def = available_tools[tool_name]
                desc = tool_def.get('function', {}).get('description', 'No description')
                print(f"{i}. {tool_name} - {desc}")
            
            print("\nEnter tool numbers separated by commas (e.g., 1,3,4):")
            choices = input("Tools: ").split(',')
            selected_tools = []
            
            for choice in choices:
                try:
                    idx = int(choice.strip()) - 1
                    if 0 <= idx < len(tool_names):
                        tool_name = tool_names[idx]
                        selected_tools.append(available_tools[tool_name])
                except ValueError:
                    continue
            
            if selected_tools:
                self.manager.selected_tools = selected_tools
                tool_names = [t.get('function', {}).get('name', 'unknown') for t in selected_tools]
                print(f"Selected tools: {', '.join(tool_names)}")
            else:
                print("No valid tools selected")
        except Exception as e:
            print(f"Error selecting tools: {e}")
    
    def view_tool_details(self):
        try:
            available_tools = self.manager.get_available_tools()
            tool_names = list(available_tools.keys())
            
            print("\nAvailable tools:")
            for i, tool_name in enumerate(tool_names, 1):
                print(f"{i}. {tool_name}")
            
            choice = input("Select tool number for details: ")
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(tool_names):
                    tool_name = tool_names[idx]
                    tool_def = available_tools[tool_name]
                    print(f"\n=== {tool_name} Details ===")
                    print(json.dumps(tool_def, indent=2))
                else:
                    print("Invalid choice")
            except ValueError:
                print("Please enter a valid number")
        except Exception as e:
            print(f"Error viewing tool details: {e}")
    
    def add_custom_tool(self):
        print("\n=== Add Custom Tool ===")
        name = input("Tool name: ")
        description = input("Tool description: ")
        
        print("Define parameters (press Enter when done):")
        parameters = {"type": "object", "properties": {}, "required": []}
        
        while True:
            param_name = input("Parameter name (or Enter to finish): ")
            if not param_name:
                break
            param_type = input(f"Type for '{param_name}' (string/number/boolean): ")
            param_desc = input(f"Description for '{param_name}': ")
            required = input(f"Is '{param_name}' required? (y/n): ").lower() == 'y'
            
            parameters["properties"][param_name] = {
                "type": param_type,
                "description": param_desc
            }
            if required:
                parameters["required"].append(param_name)
        
        tool_def = {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": parameters
            }
        }
        
        # Add to available tools
        self.manager.available_tools[name] = tool_def
        print(f"✓ Added custom tool: {name}")
    
    def chat_with_model(self):
        if not self.selected_model:
            print("Please select a model first")
            return
        
        print("\n=== Chat Configuration ===")
        print("1. Basic chat")
        print("2. Chat with tools")
        print("3. Chat with custom system message")
        print("4. Chat with custom parameters")
        
        chat_choice = input("Choice: ")
        
        use_tools = chat_choice == "2" or (chat_choice in ["3", "4"] and input("Use tools? (y/n): ").lower() == 'y')
        
        system_message = None
        if chat_choice in ["3", "4"]:
            system_message = input("Enter system message (optional): ")
            
        # Custom parameters for option 4
        options = {}
        if chat_choice == "4":
            print("Configure parameters (press Enter to skip):")
            temp = input("Temperature (0.0-2.0): ")
            if temp:
                try:
                    options['temperature'] = float(temp)
                except ValueError:
                    pass
                    
            ctx = input("Context size: ")
            if ctx.isdigit():
                options['num_ctx'] = int(ctx)
        
        print(f"\n=== Chatting with {self.selected_model} ===")
        if 'gpt-oss' in self.selected_model.lower():
            print("🧠 GPT-OSS model - Enhanced reasoning available")
            if self.manager.thinking_mode:
                print(f"💭 Thinking mode: ON (Level: {self.manager.reasoning_level})")
        
        print("Type 'quit' to exit, 'clear' to clear conversation")
        
        conversation = []
        
        while True:
            user_input = input("\n👤 You: ")
            
            if user_input.lower() == 'quit':
                break
            elif user_input.lower() == 'clear':
                conversation = []
                print("🗑️ Conversation cleared")
                continue
            
            conversation.append({"role": "user", "content": user_input})
            
            try:
                kwargs = {"use_selected_tools": use_tools}
                if system_message:
                    kwargs["system_message"] = system_message
                
                # Use different methods based on chat choice
                if chat_choice == "4" and options:
                    response = self.manager.chat_with_options(conversation, **options)
                else:
                    response = self.manager.chat(conversation, **kwargs)
                
                assistant_msg = response.get('message', {})
                content = assistant_msg.get('content', 'No content')
                
                print(f"\n🤖 Assistant: {content}")
                
                # Check for tool calls
                if 'tool_calls' in assistant_msg:
                    tool_calls = assistant_msg['tool_calls']
                    print(f"\n🔧 Tool calls made: {len(tool_calls)}")
                    for i, call in enumerate(tool_calls, 1):
                        func_name = call.get('function', {}).get('name', 'unknown')
                        func_args = call.get('function', {}).get('arguments', {})
                        print(f"  {i}. {func_name}({func_args})")
                    
                    conversation.append({
                        "role": "assistant", 
                        "content": content,
                        "tool_calls": tool_calls
                    })
                    
                    # Simulate tool execution
                    for call in tool_calls:
                        func_name = call.get('function', {}).get('name', 'unknown')
                        result = f"[Simulated result for {func_name}]"
                        conversation.append({
                            "role": "tool",
                            "tool_call_id": call.get('id', ''),
                            "content": result
                        })
                else:
                    conversation.append({"role": "assistant", "content": content})
                
            except Exception as e:
                print(f"\n❌ Error: {e}")
    
    def chat_with_options(self):
        if not self.selected_model:
            print("Please select a model first")
            return
            
        print("\n=== Chat with Custom Options ===")
        
        # Get parameters
        options = {}
        print("Configure parameters (press Enter to skip):")
        
        temp = input("Temperature (0.0-2.0): ")
        if temp:
            try:
                options['temperature'] = float(temp)
            except ValueError:
                print("Invalid temperature")
                
        ctx = input(f"Context size {list(CONTEXT_SIZES.keys())}: ")
        if ctx.isdigit():
            options['num_ctx'] = int(ctx)
            
        top_k = input("Top-k sampling: ")
        if top_k.isdigit():
            options['top_k'] = int(top_k)
            
        top_p = input("Top-p sampling (0.0-1.0): ")
        if top_p:
            try:
                options['top_p'] = float(top_p)
            except ValueError:
                print("Invalid top-p")
        
        # Single message for testing
        message = input("Enter your message: ")
        messages = [{"role": "user", "content": message}]
        
        try:
            print("Generating response with custom options...")
            response = self.manager.chat_with_options(messages, **options)
            
            content = response.get('message', {}).get('content', 'No content')
            print(f"\nResponse: {content}")
            
        except Exception as e:
            print(f"Error: {e}")
    
    def generate_text(self):
        if not self.selected_model:
            print("Please select a model first")
            return
            
        print("\n=== Generate Text ===")
        prompt = input("Enter prompt: ")
        
        print("Options:")
        print("1. Basic generation")
        print("2. Generation with custom parameters")
        print("3. Streaming generation")
        
        choice = input("Choice: ")
        
        options = {}
        stream = choice == "3"
        
        if choice == "2":
            print("Configure parameters (press Enter to skip):")
            temp = input("Temperature: ")
            if temp:
                try:
                    options['temperature'] = float(temp)
                except ValueError:
                    pass
                    
            max_tokens = input("Max tokens to predict: ")
            if max_tokens.isdigit():
                options['num_predict'] = int(max_tokens)
        
        try:
            if choice == "2":
                response = self.manager.generate_with_options(prompt, stream=stream, **options)
            else:
                response = self.manager.generate(prompt, stream=stream)
            
            if stream:
                print("\nStreaming response:")
                full_response = ""
                for chunk in response:
                    if chunk.get('response'):
                        print(chunk['response'], end='', flush=True)
                        full_response += chunk['response']
                print(f"\n\nFull response: {full_response}")
            else:
                content = response.get('response', 'No response')
                print(f"\nGenerated text: {content}")
                
        except Exception as e:
            print(f"Error: {e}")
    
    def configure_thinking_mode(self):
        print("\n=== Configure Thinking Mode ===")
        if not self.selected_model or 'gpt-oss' not in self.selected_model.lower():
            print("⚠️  Thinking mode is only available for GPT-OSS models")
            return
            
        current = self.manager.thinking_mode
        print(f"Current thinking mode: {'ON' if current else 'OFF'}")
        print(f"Current reasoning level: {self.manager.reasoning_level}")
        
        print("\n1. Toggle thinking mode")
        print("2. Set reasoning level")
        print("3. View current settings")
        
        choice = input("Choice: ")
        
        if choice == "1":
            new_mode = not current
            level = input(f"Reasoning level {REASONING_LEVELS} (current: {self.manager.reasoning_level}): ")
            if level and level in REASONING_LEVELS:
                self.manager.set_thinking_mode(new_mode, level)
            else:
                self.manager.set_thinking_mode(new_mode)
            print(f"✓ Thinking mode: {'ON' if new_mode else 'OFF'}")
        
        elif choice == "2":
            print(f"Available levels: {REASONING_LEVELS}")
            level = input("Enter level: ")
            if level in REASONING_LEVELS:
                self.manager.set_thinking_mode(self.manager.thinking_mode, level)
                print(f"✓ Reasoning level set to: {level}")
            else:
                print("Invalid level")
        
        elif choice == "3":
            print(f"Thinking mode: {self.manager.thinking_mode}")
            print(f"Reasoning level: {self.manager.reasoning_level}")
    
    def set_reasoning_level(self):
        print("\n=== Set Reasoning Level ===")
        if not self.selected_model or 'gpt-oss' not in self.selected_model.lower():
            print("⚠️  Reasoning levels are only available for GPT-OSS models")
            return
            
        print(f"Current level: {self.manager.reasoning_level}")
        print(f"Available levels: {REASONING_LEVELS}")
        
        level = input("Enter new reasoning level: ")
        if level in REASONING_LEVELS:
            self.manager.reasoning_level = level
            print(f"✓ Reasoning level set to: {level}")
        else:
            print("Invalid reasoning level")
    
    def generate_embeddings(self):
        if not self.selected_model:
            print("Please select a model first")
            return
            
        print("\n=== Generate Embeddings ===")
        print("1. Single text embedding")
        print("2. Multiple texts embedding")
        
        choice = input("Choice: ")
        
        try:
            if choice == "1":
                text = input("Enter text: ")
                response = self.manager.generate_embeddings(text)
                
                embeddings = response.get('embeddings', [[]])[0]
                print(f"✓ Generated embedding with {len(embeddings)} dimensions")
                print(f"First 10 values: {embeddings[:10]}")
                
            elif choice == "2":
                print("Enter texts (empty line to finish):")
                texts = []
                while True:
                    text = input(f"Text {len(texts)+1}: ")
                    if not text:
                        break
                    texts.append(text)
                
                if texts:
                    response = self.manager.generate_embeddings(texts)
                    embeddings = response.get('embeddings', [])
                    print(f"✓ Generated {len(embeddings)} embeddings")
                    for i, emb in enumerate(embeddings):
                        print(f"  Text {i+1}: {len(emb)} dimensions")
                        
        except Exception as e:
            print(f"Error generating embeddings: {e}")
    
    def server_information(self):
        print("\n=== Server Information ===")
        try:
            info = self.manager.get_server_info()
            
            print("🖥️  Server Details:")
            print(f"  Host: {info.get('server_host', 'Unknown')}")
            
            version = info.get('version', {})
            print(f"  Version: {version.get('version', 'Unknown')}")
            
            print(f"\n📊 Available Models: {len(info.get('available_models', {}).get('models', []))}")
            
            running = info.get('running_models', {}).get('models', [])
            print(f"🔄 Running Models: {len(running)}")
            
            for model in running:
                print(f"  - {model.get('name', 'Unknown')}")
                
        except Exception as e:
            print(f"Error getting server info: {e}")
    
    def debug_tools(self):
        print("\n=== Debug Tools ===")
        print("1. Test basic response")
        print("2. Test tool calling")
        print("3. Test manual parsing")
        print("4. View tool definitions")
        print("5. Test embedding generation")
        
        choice = input("Choice: ")
        
        if choice == "1":
            if not self.selected_model:
                print("Please select a model first")
                return
            try:
                response = self.manager.chat([
                    {"role": "user", "content": "Say 'Test successful!' and nothing else."}
                ], use_selected_tools=False)
                print("Response:", response.get('message', {}).get('content', 'No content'))
            except Exception as e:
                print(f"Error: {e}")
        
        elif choice == "2":
            if not self.selected_model:
                print("Please select a model first")
                return
            # Select calculator tool
            calc_tool = self.manager.get_available_tools().get('calculator')
            if calc_tool:
                self.manager.selected_tools = [calc_tool]
                try:
                    response = self.manager.chat([
                        {"role": "user", "content": "Calculate 15 * 8 + 42"}
                    ])
                    assistant_msg = response.get('message', {})
                    print("Response:", assistant_msg.get('content', 'No content'))
                    if 'tool_calls' in assistant_msg:
                        print("Tool calls detected:", len(assistant_msg['tool_calls']))
                except Exception as e:
                    print(f"Error: {e}")
            else:
                print("Calculator tool not available")
        
        elif choice == "3":
            # Test manual parsing
            test_responses = [
                '{"expression":"8*8*3"}',
                '{"city":"New York"}',
                '{"query":"Python programming"}'
            ]
            
            for test_raw in test_responses:
                print(f"\nTesting: {test_raw}")
                cleaned = self.manager._clean_tool_response(test_raw)
                print(f"Cleaned: {cleaned}")
                parsed = self.manager._parse_gpt_oss_tool_call(cleaned)
                print(f"Parsed: {parsed}")
        
        elif choice == "4":
            tools = self.manager.get_available_tools()
            for name, tool_def in tools.items():
                print(f"\n=== {name} ===")
                print(json.dumps(tool_def, indent=2))
        
        elif choice == "5":
            if not self.selected_model:
                print("Please select a model first")
                return
            try:
                response = self.manager.generate_embeddings("Test embedding")
                embeddings = response.get('embeddings', [[]])[0]
                print(f"✓ Generated embedding with {len(embeddings)} dimensions")
            except Exception as e:
                print(f"Error: {e}")
    
    def test_all_functions(self):
        print("\n=== Testing All Functions ===")
        
        if not self.selected_model:
            print("❌ No model selected - please select a model first")
            return
        
        tests = [
            ("Server Info", lambda: self.manager.get_server_info()),
            ("Model Info", lambda: self.manager.get_model_info()),
            ("Context Info", lambda: self.manager.get_context_info()),
            ("Running Models", lambda: self.manager.list_running_models()),
            ("Available Tools", lambda: self.manager.get_available_tools()),
            ("Basic Generation", lambda: self.manager.generate("Test prompt", num_predict=10)),
            ("Basic Chat", lambda: self.manager.chat([{"role": "user", "content": "Hello"}])),
            ("Embeddings", lambda: self.manager.generate_embeddings("Test text"))
        ]
        
        results = {}
        
        for test_name, test_func in tests:
            try:
                print(f"🧪 Testing {test_name}...")
                result = test_func()
                results[test_name] = "✅ PASSED"
                print(f"   ✅ {test_name}: PASSED")
            except Exception as e:
                results[test_name] = f"❌ FAILED: {str(e)[:50]}..."
                print(f"   ❌ {test_name}: FAILED ({str(e)[:50]}...)")
        
        print("\n📊 Test Summary:")
        for test_name, result in results.items():
            print(f"  {result}")
        
        passed = sum(1 for r in results.values() if "PASSED" in r)
        total = len(results)
        print(f"\n🎯 Overall: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    def run(self):
        print("🚀 Welcome to Ollama Manager Comprehensive Test!")
        print("This tool tests all functions in the OllamaManager class")
        
        while True:
            self.display_main_menu()
            choice = input("Enter your choice: ")
            
            if choice == "0":
                print("👋 Goodbye!")
                break
            elif choice == "1":
                self.list_models()
            elif choice == "2":
                self.select_model()
            elif choice == "3":
                self.view_model_info()
            elif choice == "4":
                self.get_context_info()
            elif choice == "5":
                self.list_running_models()
            elif choice == "6":
                self.load_unload_models()
            elif choice == "7":
                self.set_model_parameters()
            elif choice == "8":
                self.create_custom_model()
            elif choice == "9":
                self.copy_model()
            elif choice == "10":
                self.delete_model()
            elif choice == "11":
                self.pull_model()
            elif choice == "12":
                self.list_tools()
            elif choice == "13":
                self.manage_tools()
            elif choice == "14":
                self.add_custom_tool()
            elif choice == "15":
                self.chat_with_model()
            elif choice == "16":
                self.chat_with_options()
            elif choice == "17":
                self.generate_text()
            elif choice == "18":
                self.generate_text()  # Same as 17 but with different options
            elif choice == "19":
                self.configure_thinking_mode()
            elif choice == "20":
                self.set_reasoning_level()
            elif choice == "21":
                self.generate_embeddings()
            elif choice == "22":
                self.server_information()
            elif choice == "23":
                self.debug_tools()
            elif choice == "24":
                self.test_all_functions()
            else:
                print("❌ Invalid choice, please try again")

if __name__ == "__main__":
    menu = OllamaTestMenu()
    menu.run()