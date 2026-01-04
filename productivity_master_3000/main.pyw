import customtkinter as ctk
import subprocess
import winreg
import ctypes
import sys
import os
import json
import threading
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from PIL import Image
import pystray

os.chdir(os.path.dirname(os.path.abspath(__file__))) 

# --- CONFIGURATION ---
PROXY_HOST = "127.0.0.1"
PROXY_PORT = "8080"
PROXY_ADDRESS = f"{PROXY_HOST}:{PROXY_PORT}"
LOGIC_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "focus_logic_simple.py")
SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")
ICON_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "PM3000_icon.ico")
APP_NAME = "ProductivityMaster3000"
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_state.json")

# --- ADMIN CHECK ---
def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

'''
if not is_admin():
    # Relaunch the script with admin rights
    print("Requesting administrative privileges...")
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, " ".join(sys.argv), None, 1
    )
    sys.exit()
'''
# --- SYSTEM PROXY LOGIC (WINDOWS) ---
def set_windows_proxy(enable: bool):
    # Modifies Windows Registry to enable/disable system proxy

    internet_settings = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"

    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, internet_settings, 0, winreg.KEY_ALL_ACCESS)

        if enable:
            #Enable Proxy
            winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, PROXY_ADDRESS)
            # Optional: Bypass proxy for local addresses
            winreg.SetValueEx(key, "ProxyOverride", 0, winreg.REG_SZ, "<local>")
            print("System proxy enabled.")
        else:
            # Disable Proxy
            winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 0)
            print("System proxy disabled.")
        
        winreg.CloseKey(key)

        # Force system to refresh settings immediately
        ctypes.windll.wininet.InternetSetOptionW(0, 39, 0, 0) # INTERNET_OPTION_SETTINGS_CHANGED
        ctypes.windll.wininet.InternetSetOptionW(0, 37, 0, 0) # INTERNET_OPTION_REFRESH
    
    except Exception as e:
        print(f"Failed to modify system proxy settings: {e}")

# --- SETTINGS MANAGEMENT ---
class SettingManager:
    @staticmethod
    def get_default_schedule():
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        schedule = {}
        for day in days:
            if day in ["Saturday", "Sunday"]:
                schedule[day] = []
            else:
                schedule[day] = [
                    {"start": "08:00", "end": "12:00"},
                    {"start": "13:00", "end": "17:00"}
                ]
        return schedule

    @staticmethod
    def load():
        defaults = {
            "startup": False,
            "scheduler_enabled": False,
            "schedule": SettingManager.get_default_schedule(),
        }

        if not os.path.exists(SETTINGS_FILE):
            return defaults
        
        try:
            with open(SETTINGS_FILE, "r") as f:
                data = json.load(f)
                for key, val in defaults.items():
                    if key not in data:
                        data[key] = val
                return data
        except:
            return defaults
        
    @staticmethod
    def save(data):
        with open(SETTINGS_FILE, "w") as f:
            json.dump(data, f, indent=4)

# --- API UI CLASS ---
class ProductivityMaster3000App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Productivity Master 3000")
        self.geometry("400x500")
        self.resizable(False, False)

        # Load Settings
        self.settings = SettingManager.load()
        self.is_focus_active = False
        self.cooldown_active = False
        self.proxy_process = None
        self.log_file = None
        self.tray_icon = None
        self.quit_pending = False

        # --- UI Layout ---
        self.grid_columnconfigure(0, weight=1)

        # Header
        self.status_label = ctk.CTkLabel(
            self,
            text="STATUS: FREE TIME",
            font=("Roboto Medium", 20),
            text_color="green"
        )
        self.status_label.grid(row=0, column=0, pady=(20, 10))

        # The Big Button
        self.toggle_btn = ctk.CTkButton(
            self,
            text="START FOCUS",
            command=self.manual_toggle,
            width=200,
            height=50,
            font=("Roboto", 16, "bold"),
        )
        self.toggle_btn.grid(row=1, column=0, pady=10)

        # Progress Bar (Hidden initially)
        self.progress_bar = ctk.CTkProgressBar(self, width=250)
        self.progress_bar.set(0)
        self.progress_bar.grid(row=2, column=0, pady=5)
        self.progress_bar.grid_remove() # Hide initially

        # Schedule Frame
        self.sched_frame = ctk.CTkFrame(self)
        self.sched_frame.grid(row=3, column=0, pady=20, padx=20, sticky="ew")

        ctk.CTkLabel(
            self.sched_frame,
            text="Weekly Schedule Active",
            font=("Roboto", 12, "bold")
        ).grid(row=0, column=0, columnspan=2, pady=(10, 5))

        ctk.CTkLabel(
            self.sched_frame,
            text="(Edit settings.json to change times)",
            font=("Roboto", 10),
            text_color="gray"
        ).grid(row=1, column=0, columnspan=2, pady=(0, 10))

        # Enable Scheduler Switch
        self.sched_switch = ctk.CTkSwitch(self.sched_frame, text="Enable Scheduler", command=self.save_preferences)
        self.sched_switch.grid(row=2, column=0, columnspan=2, pady=5)
        if self.settings["scheduler_enabled"]: self.sched_switch.select()

        # Startup Checkbox
        self.startup_check = ctk.CTkCheckBox(self, text="Run on Startup", command=self.toggle_startup)
        self.startup_check.grid(row=3, column=0, pady=10)
        if self.settings["startup"]: self.startup_check.select()

        # --- INITIALIZATION ---
        self.write_focus_state(False)

        self.start_proxy_service()

        # --- BACKGROUND SCHEDULER ---
        self.scheduler = BackgroundScheduler()
        self.scheduler.add_job(self.check_schedule_job, 'interval', minutes=1)
        self.scheduler.start()

        # Start Tray Icon in background thread
        threading.Thread(target=self.setup_tray_icon, daemon=True).start()

        # Safety Net: handler for closing the window
        self.protocol("WM_DELETE_WINDOW", self.hide_window)

        self.after(100, self.check_schedule_job)

    def write_focus_state(self, is_active):
        try:
            with open(STATE_FILE, "w") as f:
                json.dump({"focus_active": is_active}, f)
        except Exception as e:
            print(f"Failed to write state file: {e}")

    def start_proxy_service(self):
        if self.proxy_process: return

        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE

        try:
            self.log_file = open("proxy_log.txt", "w")

            self.proxy_process = subprocess.Popen(
                ['mitmdump', '-s', LOGIC_SCRIPT],
                startupinfo=startupinfo,
                stdout=self.log_file,
                stderr=self.log_file,
            )
            print(f"Global guard started with PID: {self.proxy_process.pid}")

            set_windows_proxy(True)
        except Exception as e:
            print(f"Failed to start proxy service: {e}")

    def stop_proxy_service(self):
        set_windows_proxy(False)

        if self.proxy_process:
            self.proxy_process.terminate()
            self.proxy_process = None

        if self.log_file and not self.log_file.closed:
            self.log_file.close()

    def setup_tray_icon(self):
        # Create image for tray
        if os.path.exists(ICON_FILE):
            icon_image = Image.open(ICON_FILE)
        else:
            image = Image.new('RGB', (64, 64), color =  "red")
            icon_image = image
        
        menu = (
            pystray.MenuItem("Open", self.show_window_from_tray),
            pystray.MenuItem("Quit", self.quit_app)
        )

        self.tray_icon = pystray.Icon("PM3000", icon_image, "Productivity Master 3000", menu)
        self.tray_icon.run()

    def hide_window(self):
        self.withdraw()

    def show_window_from_tray(self, icon, item):
        self.after(0, self.deiconify)

    def quit_app(self, icon, item):
        self.after(0, self.handle_quit_request)

    def handle_quit_request(self):
        if self.is_focus_active:
            self.deiconify()
            self.quit_pending = True
            if not self.cooldown_active:
                self.initiate_cooldown()
        else:
            self.tray_icon.stop()
            self.shutdown_sequence()

    def shutdown_sequence(self):
        # Ensure cleanup on exit
        self.save_preferences()
        self.stop_proxy_service()
        self.scheduler.shutdown()
        self.destroy()
        
    def manual_toggle(self):
        if not self.is_focus_active:
            # Start Focus Mode
            self.activate_focus_mode()
        else:
            # Stop Focus Mode
            if self.cooldown_active: return
            self.quit_pending = False
            self.initiate_cooldown()

    def activate_focus_mode(self):
        self.is_focus_active = True
        self.write_focus_state(True)
        self.update_ui_state(True)

    def deactivate_focus_mode(self):
        self.is_focus_active = False
        self.write_focus_state(False)
        self.update_ui_state(False)

    def initiate_cooldown(self):
        self.cooldown_active = True
        self.toggle_btn.configure(state="disabled", fg_color="orange")
        self.status_label.configure(text="COOLING DOWN...", text_color="orange")

        # Show progress bar
        self.progress_bar.grid()
        self.progress_bar.set(0)

        # Start countdown (90 seconds)
        self.cooldown_seconds_left = 90
        self.cooldown_loop()

    def cooldown_loop(self):
        if not self.cooldown_active:
            return

        if self.cooldown_seconds_left > 0:
            # Update Button text
            self.toggle_btn.configure(text=f"UNLOCKING IN {self.cooldown_seconds_left}s")

            # Update Progress Bar (0.0 to 1.0)
            progress = (90 - self.cooldown_seconds_left) / 90
            self.progress_bar.set(progress)

            self.cooldown_seconds_left -= 1
            self.after(1000, self.cooldown_loop)
        else:
            # Cooldown finished
            self.deactivate_focus_mode()
            self.cooldown_active = False
            self.toggle_btn.configure(state="normal")
            self.progress_bar.grid_remove()

            if self.quit_pending:
                self.tray_icon.stop()
                self.shutdown_sequence()

    def update_ui_state(self, active):
        if active:
            self.toggle_btn.configure(text="STOP FOCUS", fg_color="#d63031", hover_color="#b71c1c")
            self.status_label.configure(text="STATUS: LOCKED IN", text_color="red")
        else:
            self.toggle_btn.configure(text="START FOCUS", fg_color="#1f6aa5", hover_color="#144870")
            self.status_label.configure(text="STATUS: FREE TIME", text_color="green")

    def cancel_cooldown(self):
        self.cooldown_active = False
        self.quit_pending = False
        self.progress_bar.grid_remove()
        self.toggle_btn.configure(state="normal")
        self.update_ui_state(True)

    def check_schedule_job(self):
        self.after(0, self._enforce_schedule_logic)

    # --- SCHEDULER LOGIC ---
    def _enforce_schedule_logic(self):
        #1. Check if Scheduler is enabled in the UI
        is_sched_enabled = self.sched_switch.get()

        if not is_sched_enabled:
            return

        #2. Get times
        now = datetime.now()
        day_name = now.strftime("%A")
        current_time = now.strftime("%H:%M")

        #3 Get rules for today
        day_rules = self.settings["schedule"].get(day_name, [])

        if not isinstance(day_rules, list):
            day_rules = []

        should_be_active = False

        for time_block in day_rules:
            start = time_block.get("start")
            end = time_block.get("end")

            if not start or not end:
                continue

            if start <= end:
                if start <= current_time <= end:
                    should_be_active = True
                    break
            else:
                if current_time >= start or current_time <= end:
                    should_be_active = True
                    break

        #5. Enforce
        if should_be_active:
            if self.sched_switch.cget("state") != "disabled":
                self.sched_switch.configure(state="disabled")
            
            # If not locked, LOCK IT.
            if self.cooldown_active or not self.is_focus_active:
                self.cancel_cooldown()
                self.activate_focus_mode()
        else:
            if self.sched_switch.cget("state") != "normal":
                self.sched_switch.configure(state="normal")

    def save_preferences(self):
        self.settings["startup"] = self.startup_check.get()
        self.settings["scheduler_enabled"] = self.sched_switch.get()
        SettingManager.save(self.settings)

    def toggle_startup(self):
        # 1. Save Preferences
        self.save_preferences()

        # 2. Edit Registry
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
            if self.startup_check.get() == 1:
                # Add to startup: Point to the pythonw.exe running this scripts
                # We wrap path in quotes to handle spaces
                script_path = os.path.abspath(__file__)
                cmd = f'"{sys.executable}" "{script_path}"'
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, cmd)
                print("Added to startup.")
            else:
                # Remove from startup
                try:
                    winreg.DeleteValue(key, APP_NAME)
                    print("Removed from startup.")
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception as e:
            print(f"Failed to modify startup settings: {e}")

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("blue")

    # Ensure proxy is off on start (clean slate)
    set_windows_proxy(False)

    app = ProductivityMaster3000App()
    app.mainloop()