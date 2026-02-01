import gradio as gr
import time
import subprocess
import sys
import os

class RobotMock:
    """Mock robot object for teleop controls."""
    def teleop_move(self, direction):
        """Simulates robot movement."""
        return f"🤖 Moving {direction}"
    
    def drop_block(self):
        """Simulates dropping a block."""
        return "📦 Block dropped"

def system_logic():
    """
    Main application logic container.
    """
    
    # Define default state: Not calibrated, Not disabled
    # We use a dictionary to allow mutable state passing
    default_state = {"calibrated": False, "disabled": False}
    
    # Initialize robot mock
    robot = RobotMock()
    
    # Map keyboard keys to robot commands
    teleop_commands = {
        'w': lambda: robot.teleop_move('Forward'),
        's': lambda: robot.teleop_move('Backward'),
        'a': lambda: robot.teleop_move('Left'),
        'd': lambda: robot.teleop_move('Right'),
        'u': lambda: robot.teleop_move('Up'),
        'j': lambda: robot.teleop_move('Down'),
        'o': lambda: robot.drop_block(),
    }

    def process_chat(user_message, history, state):
        """
        Handles chat interaction and inference generation.
        """
        # Ensure history is initialized
        if history is None:
            history = []

        # Normalize older tuple-format histories to messages format
        if len(history) > 0 and isinstance(history[0], (list, tuple)):
            normalized = []
            for user_msg, bot_msg in history:
                normalized.append({"role": "user", "content": user_msg})
                normalized.append({"role": "assistant", "content": bot_msg})
            history = normalized

        if state["disabled"]:
            # If system is disabled, prevent chat and return warning in messages format
            history.append({"role": "user", "content": user_message})
            history.append({"role": "assistant", "content": "⛔ SYSTEM DISABLED. MESSAGE REJECTED."})
            return history, "System is offline.", ""

        if not user_message.strip():
            return history, "", ""

        # Simulate chatbot logic
        bot_response = f"I received: {user_message}"

        # Append messages in the dict format expected by newer Gradio versions
        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": bot_response})

        # Simulate "Inference" processing (Feature 3)
        inference_data = f"ANALYSIS: Input length {len(user_message)} chars.\nINTENT: General Query.\nSTATUS: Processed successfully."

        return history, inference_data, ""

    def run_calibration(state):
        """
        Runs the external `calibrate.py` script and waits for it to finish.
        """
        if state["disabled"]:
            return "❌ System Disabled. Calibration Failed.", state
        try:
            script_path = os.path.join(os.path.dirname(__file__), "calibrate.py")
            # Run the calibration script using the same Python executable and wait for completion
            result = subprocess.run([sys.executable, script_path], check=True, capture_output=True, text=True)
            state["calibrated"] = True
            timestamp = time.strftime("%H:%M:%S")
            stdout = result.stdout.strip()
            if stdout:
                return f"✅ System Calibrated at {timestamp}\n\n{stdout}", state
            return f"✅ System Calibrated at {timestamp}", state
        except subprocess.CalledProcessError as e:
            err = e.stderr.strip() if e.stderr else str(e)
            return f"❌ Calibration script failed: {err}", state
        except Exception as e:
            return f"❌ Calibration failed: {e}", state

    def auto_calibrate_on_load(state):
        """
        Triggered automatically when the page loads (Feature 2).
        Checks if already calibrated to avoid re-calibrating on simple refreshes if state persists.
        """
        if not state["calibrated"] and not state["disabled"]:
            msg, new_state = run_calibration(state)
            return msg, new_state
        return "System Ready (Cached)", state

    def handle_signal(signal_code, state):
        """
        Handles the specific signal to disable functionality (Feature 4).
        Specific Signal is: 'STOP'
        """
        if signal_code.strip().upper() == "STOP":
            state["disabled"] = True
            
            # Return values to update UI components:
            # 1. Status Message
            # 2. State
            # 3. Chat Input (interactive=False)
            # 4. Calibrate Button (interactive=False)
            # 5. Signal Button (interactive=False)
            return (
                "⚠ SYSTEM SHUTDOWN SIGNAL RECEIVED. ALL OPERATIONS CEASED.", 
                state,
                gr.update(interactive=False, placeholder="System Disabled"),
                gr.update(interactive=False, value="Disabled"),
                gr.update(interactive=False)
            )
        
        return f"Signal '{signal_code}' ignored.", state, gr.update(), gr.update(), gr.update()

    def execute_teleop_command(key_or_direction):
        """
        Execute teleop command based on key or direction button press.
        """
        if key_or_direction in teleop_commands:
            result = teleop_commands[key_or_direction]()
            return f"✅ {result}"
        return "❌ Invalid command"

    # --- GUI Layout ---
    with gr.Blocks(title="Control Interface") as demo:
        # State variable to hold system status across interactions within a session
        system_state = gr.State(default_state)
        
        gr.Markdown("# 🤖 System Control Interface")
        
        with gr.Row():
            with gr.Column(scale=2):
                # Feature 1: Chatbot
                # Removed 'type="messages"' to fix TypeError. 
                # This component will now expect [[user_msg, bot_msg], ...] format.
                chatbot = gr.Chatbot(label="Conversation Log", height=400)
                msg_input = gr.Textbox(
                    label="User Input", 
                    placeholder="Type a message...",
                    interactive=True
                )
                clear = gr.ClearButton([msg_input, chatbot])

            with gr.Column(scale=1):
                # Feature 2 & 4: Controls and Status
                gr.Markdown("### System Status")
                
                # Feature 2: Calibration Button
                calibrate_btn = gr.Button("📡 Send Calibration Signal", variant="primary")
                
                # Feature 3: Inference Display
                inference_output = gr.TextArea(
                    label="Inference / Processing Output", 
                    interactive=False,
                    lines=5
                )

                gr.Markdown("---")
                gr.Markdown("### Admin Controls")
                
                # Feature 4: Disable Functionality
                signal_input = gr.Textbox(
                    label="Control Signal", 
                    placeholder="Enter signal code (e.g. STOP)"
                )
                signal_btn = gr.Button("Transmit Signal", variant="stop")

        # --- Robot Teleop Control Panel ---
        gr.Markdown("### 🎮 Robot Teleop Controls")
        gr.Markdown("**Keyboard:** W/A/S/D (Move), U (Up), J (Down), O (Drop)")
        
        with gr.Row():
            teleop_forward = gr.Button("⬆️ W", size="lg")
            teleop_output = gr.Textbox(label="Command Output", interactive=False, lines=2)
        
        with gr.Row():
            teleop_left = gr.Button("⬅️ A", size="lg")
            teleop_down = gr.Button("⬇️ S", size="lg")
            teleop_right = gr.Button("➡️ D", size="lg")
        
        with gr.Row():
            teleop_up = gr.Button("⬆️ U", size="lg")
            teleop_drop = gr.Button("📦 O", size="lg")

        # --- Event Wiring ---

        # 1. Chat Interaction
        msg_input.submit(
            process_chat, 
            inputs=[msg_input, chatbot, system_state], 
            outputs=[chatbot, inference_output, msg_input]
        )

        # 2. Manual Calibration
        calibrate_btn.click(
            run_calibration,
            inputs=[system_state],
            outputs=[inference_output, system_state]
        )

        # 3. Automatic Calibration on Page Load
        # This triggers immediately when the browser loads the interface
        demo.load(
            auto_calibrate_on_load,
            inputs=[system_state],
            outputs=[inference_output, system_state]
        )

        # 4. Signal Handling (Disable functionality)
        signal_btn.click(
            handle_signal,
            inputs=[signal_input, system_state],
            outputs=[
                inference_output, # Update status area
                system_state,     # Update internal state
                msg_input,        # Disable chat input
                calibrate_btn,    # Disable calibrate button
                signal_btn        # Disable signal button itself
            ]
        )

        # 5. Teleop Button Controls
        teleop_forward.click(execute_teleop_command, inputs=gr.State('w'), outputs=teleop_output)
        teleop_left.click(execute_teleop_command, inputs=gr.State('a'), outputs=teleop_output)
        teleop_down.click(execute_teleop_command, inputs=gr.State('s'), outputs=teleop_output)
        teleop_right.click(execute_teleop_command, inputs=gr.State('d'), outputs=teleop_output)
        teleop_up.click(execute_teleop_command, inputs=gr.State('u'), outputs=teleop_output)
        teleop_drop.click(execute_teleop_command, inputs=gr.State('o'), outputs=teleop_output)

        # 6. Keyboard input handler with JavaScript
        def register_keyboard_handler():
            return """
            <script>
            document.addEventListener('keydown', (e) => {
                const key = e.key.toLowerCase();
                const commands = ['w', 'a', 's', 'd', 'u', 'j', 'o'];
                if (commands.includes(key)) {
                    const buttons = document.querySelectorAll('[data-testid="button"]');
                    const buttonMap = {
                        'w': 0,
                        'a': 1,
                        's': 2,
                        'd': 3,
                        'u': 4,
                        'j': 5,
                        'o': 6
                    };
                    if (buttonMap[key] !== undefined && buttons[buttonMap[key]]) {
                        buttons[buttonMap[key]].click();
                    }
                }
            });
            </script>
            """
        
        demo.load(lambda: None, outputs=gr.HTML(register_keyboard_handler()))

    return demo

if __name__ == "__main__":
    app = system_logic()
    app.launch()