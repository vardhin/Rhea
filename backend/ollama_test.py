from ollama_module import OllamaManager
import json

class OllamaTestMenu:
    def __init__(self):
        self.manager = OllamaManager()
        self.selected_model = None
        self.available_models = []
        
    def display_main_menu(self):
        print("\n" + "="*50)
        print("OLLAMA MANAGER TEST MENU")
        print("="*50)
        print("1. List available models")
        print("2. Select a model")
        print("3. View current model info")
        print("4. List available tools")
        print("5. Select/manage tools")
        print("6. Add custom tool")
        print("7. Configure model settings")
        print("8. Chat with model")
        print("9. Debug tool format issues")
        print("0. Exit")
        print("-"*50)
        
    def list_models(self):
        print("\n=== Available Models ===")
        self.available_models = self.manager.list_models()
        if not self.available_models:
            print("No models found!")
            return
            
        for i, model in enumerate(self.available_models):
            print(f"{i+1}. {model.get('name', 'Unknown')}")
            if model.get('size'):
                print(f"   Size: {model.get('size')}")
            if model.get('modified_at'):
                print(f"   Modified: {model.get('modified_at')}")
            print()
    
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
                    supports_tools = self.manager.is_gpt_oss_model() or 'gpt' in model_name.lower()
                    print(f"Tool support: {'Yes' if supports_tools else 'No'}")
                    if self.manager.is_gpt_oss_model():
                        print("Note: GPT-OSS model detected - will use optimized manual tool parsing")
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
            
        print(f"Selected model: {self.selected_model}")
        info = self.manager.get_model_info()
        print(f"Model info: {info}")
        print(f"Supports tools: {self.manager.is_gpt_oss_model() or 'gpt' in self.selected_model.lower()}")
        print(f"Is GPT-OSS: {self.manager.is_gpt_oss_model()}")
        if self.manager.is_gpt_oss_model():
            print("Note: Uses optimized manual tool parsing (skips automatic parsing)")
    
    def list_tools(self):
        print("\n=== Available Tools ===")
        tools = self.manager.list_tool_names()
        for i, tool in enumerate(tools, 1):
            print(f"{i}. {tool}")
        
        selected = self.manager.get_selected_tool_names()
        if selected:
            print(f"\nCurrently selected: {', '.join(selected)}")
        else:
            print("\nNo tools currently selected")
    
    def manage_tools(self):
        print("\n=== Tool Management ===")
        print("1. Select tools")
        print("2. View selected tools")
        print("3. Clear selected tools")
        
        choice = input("Choice: ")
        
        if choice == "1":
            self.select_tools()
        elif choice == "2":
            selected = self.manager.get_selected_tool_names()
            print(f"Selected tools: {', '.join(selected) if selected else 'None'}")
        elif choice == "3":
            self.manager.clear_selected_tools()
            print("Cleared all selected tools")
    
    def select_tools(self):
        available_tools = self.manager.list_tool_names()
        print("\nAvailable tools:")
        for i, tool in enumerate(available_tools, 1):
            print(f"{i}. {tool}")
        
        print("\nEnter tool numbers separated by commas (e.g., 1,3,4):")
        try:
            choices = input("Tools: ").split(',')
            selected_tools = []
            for choice in choices:
                idx = int(choice.strip()) - 1
                if 0 <= idx < len(available_tools):
                    selected_tools.append(available_tools[idx])
            
            if selected_tools:
                self.manager.select_tools(selected_tools)
                print(f"Selected tools: {', '.join(selected_tools)}")
            else:
                print("No valid tools selected")
        except ValueError:
            print("Invalid input format")
    
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
        
        self.manager.add_tool(name, tool_def)
        print(f"✓ Added custom tool: {name}")
    
    def configure_settings(self):
        print("\n=== Model Configuration ===")
        if not self.manager.is_gpt_oss_model():
            print("Current model is not GPT-OSS, limited configuration available")
            return
        
        print("1. Toggle thinking mode")
        print("2. Set reasoning level")
        print("3. View current settings")
        
        choice = input("Choice: ")
        
        if choice == "1":
            current = getattr(self.manager, 'thinking_mode', False)
            new_mode = not current
            self.manager.set_thinking_mode(new_mode)
            print(f"Thinking mode: {'ON' if new_mode else 'OFF'}")
        
        elif choice == "2":
            print("Reasoning levels: low, medium, high")
            level = input("Enter level: ")
            if level in ["low", "medium", "high"]:
                self.manager.set_reasoning_level(level)
                print(f"Reasoning level set to: {level}")
            else:
                print("Invalid level")
        
        elif choice == "3":
            thinking = getattr(self.manager, 'thinking_mode', False)
            reasoning = getattr(self.manager, 'reasoning_level', 'unknown')
            print(f"Thinking mode: {thinking}")
            print(f"Reasoning level: {reasoning}")
    
    def chat_with_model(self):
        if not self.selected_model:
            print("Please select a model first")
            return
        
        print("\n=== Chat Configuration ===")
        print("1. Chat with tools (if available)")
        print("2. Chat without tools")
        print("3. Chat with custom system message")
        
        chat_choice = input("Choice: ")
        use_tools = chat_choice == "1"
        
        system_message = None
        if chat_choice == "3":
            system_message = input("Enter system message: ")
            use_tools = input("Use tools? (y/n): ").lower() == 'y'
        
        # Show optimization info for GPT-OSS
        if self.manager.is_gpt_oss_model() and use_tools:
            print("Note: GPT-OSS model - using optimized manual tool parsing")
        
        print(f"\n=== Chatting with {self.selected_model} ===")
        print("Type 'quit' to exit chat")
        
        conversation = []
        
        while True:
            user_input = input("\nYou: ")
            if user_input.lower() == 'quit':
                break
            
            conversation.append({"role": "user", "content": user_input})
            
            try:
                kwargs = {"use_selected_tools": use_tools}
                if system_message:
                    kwargs["system_message"] = system_message
                
                response = self.manager.chat(conversation, **kwargs)
                
                assistant_msg = response.get('message', {})
                content = assistant_msg.get('content', 'No content')
                
                print(f"\nAssistant: {content}")
                
                # Check for tool calls
                if 'tool_calls' in assistant_msg:
                    tool_calls = assistant_msg['tool_calls']
                    print(f"\n🔧 Tool calls made:")
                    for i, call in enumerate(tool_calls, 1):
                        func_name = call.get('function', {}).get('name', 'unknown')
                        func_args = call.get('function', {}).get('arguments', {})
                        print(f"  {i}. {func_name}({func_args})")
                    
                    # Add tool call to conversation
                    conversation.append({
                        "role": "assistant", 
                        "content": content,
                        "tool_calls": tool_calls
                    })
                    
                    # Simulate tool results (in real implementation, you'd execute the tools)
                    print("\n💡 Tool execution simulation (replace with real implementation):")
                    for call in tool_calls:
                        func_name = call.get('function', {}).get('name', 'unknown')
                        if func_name == 'calculate':
                            args = call.get('function', {}).get('arguments', {})
                            expr = args.get('expression', '')
                            try:
                                result = str(eval(expr))  # Note: eval is unsafe, use proper math parser
                                print(f"  {func_name}: {expr} = {result}")
                                conversation.append({
                                    "role": "tool",
                                    "tool_call_id": call.get('id', ''),
                                    "content": f"Result: {result}"
                                })
                            except:
                                print(f"  {func_name}: Error calculating {expr}")
                        else:
                            print(f"  {func_name}: [Tool not implemented in test]")
                else:
                    conversation.append({"role": "assistant", "content": content})
                
            except Exception as e:
                print(f"\nError: {e}")
    
    def debug_tools(self):
        print("\n=== Debug Tool Format Issues ===")
        if not self.selected_model:
            print("Please select a model first")
            return
        
        if self.manager.is_gpt_oss_model():
            print("GPT-OSS model detected - uses optimized manual parsing")
        else:
            print("Non-GPT-OSS model - uses standard tool parsing")
        
        print("\n1. Test simple response (no tools)")
        print("2. Test tool calling with calculator")
        print("3. View selected tool definitions")
        print("4. Test raw error extraction")
        
        choice = input("Choice: ")
        
        if choice == "1":
            try:
                response = self.manager.chat([
                    {"role": "user", "content": "Say 'Hello, I am working correctly!'"}
                ], use_selected_tools=False)
                print("Response:", response.get('message', {}).get('content', 'No content'))
            except Exception as e:
                print(f"Error: {e}")
        
        elif choice == "2":
            print("Testing calculator tool...")
            self.manager.select_tools(["calculator"])
            try:
                response = self.manager.chat([
                    {"role": "user", "content": "Calculate 15 * 8 + 42"}
                ])
                assistant_msg = response.get('message', {})
                print("Response:", assistant_msg.get('content', 'No content'))
                if 'tool_calls' in assistant_msg:
                    print("Tool calls detected:", assistant_msg['tool_calls'])
            except Exception as e:
                print(f"Error: {e}")
                if "raw=" in str(e):
                    raw_part = str(e).split("raw='")[1].split("'")[0]
                    print(f"Raw response: {raw_part}")
        
        elif choice == "3":
            selected_tools = self.manager.get_selected_tool_names()
            print(f"Selected tools: {selected_tools}")
            for tool_name in selected_tools:
                tool_def = self.manager.get_tool_info(tool_name)
                print(f"\n{tool_name} definition:")
                print(json.dumps(tool_def, indent=2))
        
        elif choice == "4":
            # Test the manual parsing directly
            test_raw = '{"expression":"8*8*3"}<|call|>commentary<|channel|>commentary'
            print(f"Test raw response: {test_raw}")
            cleaned = self.manager._clean_tool_response(test_raw)
            print(f"Cleaned response: {cleaned}")
            parsed = self.manager._parse_gpt_oss_tool_call(cleaned)
            print(f"Parsed tool call: {parsed}")
    
    def run(self):
        print("Welcome to Ollama Manager Interactive Test!")
        print("Optimized for GPT-OSS models with manual tool parsing")
        
        while True:
            self.display_main_menu()
            choice = input("Enter your choice: ")
            
            if choice == "0":
                print("Goodbye!")
                break
            elif choice == "1":
                self.list_models()
            elif choice == "2":
                self.select_model()
            elif choice == "3":
                self.view_model_info()
            elif choice == "4":
                self.list_tools()
            elif choice == "5":
                self.manage_tools()
            elif choice == "6":
                self.add_custom_tool()
            elif choice == "7":
                self.configure_settings()
            elif choice == "8":
                self.chat_with_model()
            elif choice == "9":
                self.debug_tools()
            else:
                print("Invalid choice, please try again")

if __name__ == "__main__":
    menu = OllamaTestMenu()
    menu.run()