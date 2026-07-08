import tkinter as tk
from tkinter import ttk, messagebox
import json
import time
import psutil
import threading
from typing import Dict
import os
import subprocess
from datetime import datetime

class KeyBindingApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Key Binding Configuration")
        self.running = False
        self.thread = None
        
        # Main container
        self.main_frame = ttk.Frame(root, padding="10")
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Profile section
        self.setup_profile_section()
        
        # Process selection section
        self.setup_process_section()
        
        # Function keys configuration
        self.key_configs: Dict[str, Dict] = {}
        self.setup_function_keys()
        
        # Control buttons
        self.setup_control_buttons()

    def setup_profile_section(self):
        profile_frame = ttk.LabelFrame(self.main_frame, text="Profile", padding="5")
        profile_frame.grid(row=0, column=0, columnspan=4, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(profile_frame, text="Profile Name:").grid(row=0, column=0, padx=5)
        self.profile_name = ttk.Entry(profile_frame)
        self.profile_name.grid(row=0, column=1, padx=5)
        
        ttk.Button(profile_frame, text="Save", command=self.save_profile).grid(row=0, column=2, padx=5)
        ttk.Button(profile_frame, text="Load", command=self.load_profile).grid(row=0, column=3, padx=5)

    def setup_process_section(self):
        process_frame = ttk.LabelFrame(self.main_frame, text="Process Selection", padding="5")
        process_frame.grid(row=1, column=0, columnspan=4, sticky=(tk.W, tk.E), pady=5)
        
        self.process_listbox = tk.Listbox(process_frame, height=3)
        self.process_listbox.grid(row=0, column=0, sticky=(tk.W, tk.E))
        ttk.Button(process_frame, text="Refresh", command=self.refresh_processes).grid(row=0, column=1)
        
        self.refresh_processes()

    def setup_function_keys(self):
        keys_frame = ttk.LabelFrame(self.main_frame, text="Function Keys", padding="5")
        keys_frame.grid(row=2, column=0, columnspan=4, sticky=(tk.W, tk.E), pady=5)
        
        for i in range(12):
            key = f"F{i+1}"
            self.key_configs[key] = {}
            
            row = i // 3
            col = i % 3
            
            key_frame = ttk.Frame(keys_frame)
            key_frame.grid(row=row, column=col, padx=5, pady=5)
            
            ttk.Label(key_frame, text=key).grid(row=0, column=0)
            
            delay_var = tk.StringVar(value="1.0")
            enable_var = tk.BooleanVar(value=False)
            
            ttk.Entry(key_frame, textvariable=delay_var, width=8).grid(row=0, column=1)
            ttk.Checkbutton(key_frame, text="Enable", variable=enable_var).grid(row=0, column=2)
            
            self.key_configs[key] = {
                "delay": delay_var,
                "enable": enable_var
            }

    def setup_control_buttons(self):
        control_frame = ttk.Frame(self.main_frame)
        control_frame.grid(row=3, column=0, columnspan=4, pady=10)
        
        self.toggle_button = ttk.Button(control_frame, text="ENABLE", command=self.toggle_execution)
        self.toggle_button.grid(row=0, column=0, padx=5)

    def refresh_processes(self):
        self.process_listbox.delete(0, tk.END)
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if 'ROSE' in proc.info['name'].upper():
                    self.process_listbox.insert(tk.END, f"{proc.info['pid']} - {proc.info['name']}")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

    def save_profile(self):
        if not self.profile_name.get():
            messagebox.showerror("Error", "Please enter a profile name")
            return
            
        config = {
            "profile_name": self.profile_name.get(),
            "keys": {
                key: {
                    "delay": float(self.key_configs[key]["delay"].get()),
                    "enable": self.key_configs[key]["enable"].get()
                }
                for key in self.key_configs
            }
        }
        
        with open(f"{self.profile_name.get()}.json", "w") as f:
            json.dump(config, f)
        
        messagebox.showinfo("Success", "Profile saved successfully")

    def load_profile(self):
        try:
            with open(f"{self.profile_name.get()}.json", "r") as f:
                config = json.load(f)
            
            for key, values in config["keys"].items():
                self.key_configs[key]["delay"].set(str(values["delay"]))
                self.key_configs[key]["enable"].set(values["enable"])
                
            messagebox.showinfo("Success", "Profile loaded successfully")
        except FileNotFoundError:
            messagebox.showerror("Error", "Profile not found")

    def generate_ahk_script(self):
        selected_index = self.process_listbox.curselection()
        if not selected_index:
            messagebox.showerror("Error", "Please select a process")
            return None
            
        process_info = self.process_listbox.get(selected_index[0])
        process_pid = process_info.split('-')[0].strip()

        # Generate unique script name
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        profile_name = self.profile_name.get() or "unnamed"
        script_name = f"script_{profile_name}_{process_pid}_{timestamp}.ahk"

        script_content = [
            '#SingleInstance Force',
            '#NoEnv',
            'SetWorkingDir %A_ScriptDir%',
            '',
            f'global targetPID := {process_pid}',
            '',
            'Loop',
            '{',
            '    if ProcessExist(targetPID)',
            '    {'
        ]

        # Add enabled function keys
        for key, config in self.key_configs.items():
            if config["enable"].get():
                try:
                    delay = int(float(config["delay"].get()) * 1000)  # Convert to milliseconds
                    script_content.extend([
                        f'        ControlSend,, {{{key}}}, ahk_pid %targetPID%',
                        f'        Sleep {delay}'
                    ])
                except ValueError:
                    messagebox.showerror("Error", f"Invalid delay value for {key}")
                    return None

        # Add closing brackets and helper functions
        script_content.extend([
            '    }',
            '}',
            '',
            'ProcessExist(PID)',
            '{',
            '    Process, Exist, %PID%',
            '    return ErrorLevel',
            '}',
            '',
            '^Esc::ExitApp'
        ])

        # Write script to file
        with open(script_name, "w", encoding='utf-8') as f:
            f.write('\n'.join(script_content))

        return script_name


    def execute_keystrokes(self):
        script_path = self.generate_ahk_script()
        if not script_path:
            self.running = False
            self.toggle_button.config(text="ENABLE")
            return

        try:
            # Try to find AutoHotkey executable in common locations
            ahk_paths = [
                r"C:\Program Files\AutoHotkey\AutoHotkey.exe",
                r"C:\Program Files (x86)\AutoHotkey\AutoHotkey.exe",
                "AutoHotkey.exe"  # If it's in PATH
            ]

            ahk_exe = None
            for path in ahk_paths:
                if os.path.exists(path):
                    ahk_exe = path
                    break

            if not ahk_exe:
                messagebox.showerror("Error", "AutoHotkey not found. Please install it first.")
                self.running = False
                self.toggle_button.config(text="ENABLE")
                return

            # Store the script path for cleanup
            self.current_script_path = script_path

            # Run the script
            self.ahk_process = subprocess.Popen([ahk_exe, script_path])

            # Monitor the process
            while self.running:
                if self.ahk_process.poll() is not None:  # Process has ended
                    break
                time.sleep(0.1)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to execute AHK script: {str(e)}")
            self.running = False
            self.toggle_button.config(text="ENABLE")

    def toggle_execution(self):
        self.running = not self.running
        
        if self.running:
            self.toggle_button.config(text="DISABLE")
            self.thread = threading.Thread(target=self.execute_keystrokes, daemon=True)
            self.thread.start()
        else:
            self.toggle_button.config(text="ENABLE")
            if hasattr(self, 'ahk_process'):
                self.ahk_process.terminate()
                time.sleep(0.5)  # Give some time for the script to terminate
                # Clean up current script
                if hasattr(self, 'current_script_path') and os.path.exists(self.current_script_path):
                    try:
                        os.remove(self.current_script_path)
                    except:
                        pass

def main():
    root = tk.Tk()
    app = KeyBindingApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()