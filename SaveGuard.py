# SaveGuard.py
import sys
import os
import subprocess
import importlib.util
from datetime import datetime

# Setup log directory and log file name at the very beginning
if getattr(sys, "frozen", False):
    # Running as compiled executable
    SCRIPT_DIR = os.path.dirname(sys.executable)
else:
    # Running as a normal Python script
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

LOGS_DIR = os.path.join(SCRIPT_DIR, "Logs")
os.makedirs(LOGS_DIR, exist_ok=True)
startup_time = datetime.now().strftime("%Y-%m-%d--%H-%M-%S")
LOG_FILE = os.path.join(LOGS_DIR, f"{startup_time}_Log.txt")


def log(msg):
    # Generate timestamp string
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    full_msg = f"[{timestamp}] {msg}"

    # Print to console and append to log file, flushing immediately
    print(full_msg, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(full_msg + "\n")
        f.flush()
        os.fsync(f.fileno())


REQUIRED_PACKAGES = {
    "cv2": "opencv-python",
    "numpy": "numpy",
    "keyboard": "keyboard",
    "mss": "mss",
}

# Print current Python version into the log
log(f"Python version: {sys.version}")

# Check and install missing required libraries automatically
for module, package in REQUIRED_PACKAGES.items():
    if importlib.util.find_spec(module) is None:
        log(f"Installing missing package: {package}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])

import time
import shutil
import threading
import cv2
import numpy as np
import keyboard
import json
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
from mss import MSS
import signal

# Load config
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.txt")
with open(CONFIG_PATH, "r") as f:
    config = json.load(f)

# Global variables loaded from config
SRC_DIR = config["SRC_DIR"]
DST_DIR = os.path.join(SCRIPT_DIR, config["BACKUP_FOLDER"])
IMG_PATH = os.path.join(SCRIPT_DIR, config["IMG_NAME"])
MONITOR_ROI = config["MONITOR_ROI"]

# Load new screenshot mode and hotkey parameters with safe defaults
SCREENSHOT_MODE = config.get("SCREENSHOT_MODE", "Auto")
SCREENSHOT_HOTKEY = config.get("SCREENSHOT_HOTKEY", "]")
EXIT_HOTKEY = config.get("EXIT_HOTKEY", "f10")

running = True
trigger_correlation = threading.Event()
trigger_manual_screenshot = threading.Event()
current_hotkey_hook = None
current_exit_hook = None

# Global variables for GUI state updates and backup tracking
last_backup_time_str = "None"
app_state = "IDLE"  # States: IDLE, SCANNING, SUCCESS
blink_toggle = False
latest_backup_target_dir = DST_DIR


def stop_all(*args):
    global running
    if not running:
        return

    log("Terminating all tasks and closing...")

    running = False
    trigger_correlation.set()

    # Forcefully and safely kill the entire process and all threads
    os._exit(0)


def backup_task():
    global last_backup_time_str, latest_backup_target_dir

    while running:
        try:
            # Ensure base destination directory exists
            os.makedirs(DST_DIR, exist_ok=True)

            # Walk through the source directory recursively
            for root_dir, _, files in os.walk(SRC_DIR):
                for f in files:
                    path = os.path.join(root_dir, f)

                    # Calculate relative path to maintain folder structure
                    rel_path = os.path.relpath(root_dir, SRC_DIR)
                    if rel_path == ".":
                        current_target_dir = DST_DIR
                    else:
                        current_target_dir = os.path.join(DST_DIR, rel_path)

                    # Ensure the target subdirectory exists
                    os.makedirs(current_target_dir, exist_ok=True)

                    mtime = os.path.getmtime(path)
                    date_str = datetime.fromtimestamp(mtime).strftime("%Y%m%d_%H%M%S")
                    target_path = os.path.join(current_target_dir, f"{date_str}_{f}")

                    if not os.path.exists(target_path):
                        # Copy file to the dynamically created destination folder
                        shutil.copy2(path, target_path)
                        log_path = f if rel_path == "." else os.path.join(rel_path, f)
                        log(f"Backed up: {log_path}. Triggering image correlation.")

                        # Update globals for screenshot saving and GUI
                        latest_backup_target_dir = current_target_dir
                        last_backup_time_str = datetime.now().strftime("%H:%M:%S")
                        trigger_correlation.set()

        except Exception as e:
            # Log any file system errors to prevent thread crash
            log(f"Backup task encountered an error: {e}")

        time.sleep(1)


def image_task():
    global app_state
    # Use MSS() instead of mss() to fix the deprecation warning
    sct = MSS()

    while running:
        if not trigger_correlation.is_set():
            trigger_correlation.wait(timeout=1.0)
            continue

        # Start scanning state and reset manual screenshot trigger
        log(f"New backup detected. Mode: {SCREENSHOT_MODE}. Starting scan/wait...")
        app_state = "SCANNING"
        trigger_manual_screenshot.clear()

        template = None
        if SCREENSHOT_MODE == "Auto":
            # In automatic mode, we need the template image to proceed
            if not os.path.exists(IMG_PATH):
                log(f"Image not found at: {IMG_PATH}")
                app_state = "FAILED"
                trigger_correlation.clear()
                continue
            template = cv2.imread(IMG_PATH, cv2.IMREAD_GRAYSCALE)

        while trigger_correlation.is_set() and running:
            if SCREENSHOT_MODE == "Auto":
                screen = np.array(sct.grab(MONITOR_ROI))
                gray = cv2.cvtColor(screen, cv2.COLOR_BGRA2GRAY)

                # Process correlation match
                res = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, _ = cv2.minMaxLoc(res)
                log(f"Current image correlation: {max_val * 100:.2f}%")

                if max_val > 0.9:
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    # Save screenshot in the exact subdirectory where the save occurred
                    screenshot_path = os.path.join(
                        latest_backup_target_dir, f"{ts}_Screenshot.png"
                    )

                    sct.shot(mon=2, output=screenshot_path)
                    log(f"Threshold reached! Screenshot saved: {screenshot_path}")

                    app_state = "SUCCESS"
                    # Clear trigger only on success, otherwise keep scanning
                    trigger_correlation.clear()
                else:
                    log(f"Image not found on screen yet. Retrying...")

                time.sleep(1)

            elif SCREENSHOT_MODE == "Hotkey":
                # Wait for the manual hotkey event to be triggered by the user
                if trigger_manual_screenshot.is_set():
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    # Save screenshot in the exact subdirectory where the save occurred
                    screenshot_path = os.path.join(
                        latest_backup_target_dir, f"{ts}_Screenshot.png"
                    )

                    sct.shot(mon=2, output=screenshot_path)
                    log(f"Manual hotkey pressed! Screenshot saved: {screenshot_path}")

                    app_state = "SUCCESS"
                    trigger_manual_screenshot.clear()
                    trigger_correlation.clear()
                else:
                    time.sleep(0.1)


def manual_screenshot_callback():
    # Trigger event if we are in hotkey mode and currently waiting for screenshot
    if app_state == "SCANNING" and SCREENSHOT_MODE == "Hotkey":
        trigger_manual_screenshot.set()


def apply_config():
    global SRC_DIR, DST_DIR, IMG_PATH, MONITOR_ROI, SCREENSHOT_MODE, SCREENSHOT_HOTKEY, current_hotkey_hook
    global EXIT_HOTKEY, current_exit_hook, latest_backup_target_dir

    # Check if the specified image file exists on disk (Only needed in Auto mode)
    temp_img_path = os.path.join(SCRIPT_DIR, img_name_var.get())
    if mode_var.get() == "Auto" and not os.path.exists(temp_img_path):
        log(
            f"Validation Error: Image not found at {temp_img_path}. Switching to Hotkey mode."
        )
        messagebox.showwarning(
            "Image Not Found",
            f"The configured image file was not found:\n{temp_img_path}\n\nSwitching to 'Hotkey' mode automatically.",
        )
        mode_var.set("Hotkey")

    # Apply new GUI values to global memory variables
    SRC_DIR = src_dir_var.get()
    DST_DIR = os.path.join(SCRIPT_DIR, backup_folder_var.get())
    latest_backup_target_dir = DST_DIR
    IMG_PATH = temp_img_path
    MONITOR_ROI = {
        "top": int(roi_top_var.get()),
        "left": int(roi_left_var.get()),
        "width": int(roi_width_var.get()),
        "height": int(roi_height_var.get()),
    }
    SCREENSHOT_MODE = mode_var.get()

    # Apply hotkey logic and rebind if user changed the key
    new_hotkey = hotkey_var.get()
    if new_hotkey != SCREENSHOT_HOTKEY or current_hotkey_hook is None:
        if current_hotkey_hook:
            keyboard.remove_hotkey(current_hotkey_hook)

        SCREENSHOT_HOTKEY = new_hotkey
        current_hotkey_hook = keyboard.add_hotkey(
            SCREENSHOT_HOTKEY, manual_screenshot_callback
        )

    # Apply exit hotkey logic
    new_exit_hotkey = exit_hotkey_var.get()
    if new_exit_hotkey != EXIT_HOTKEY or current_exit_hook is None:
        if current_exit_hook:
            keyboard.remove_hotkey(current_exit_hook)

        EXIT_HOTKEY = new_exit_hotkey
        current_exit_hook = keyboard.add_hotkey(EXIT_HOTKEY, stop_all)

    return True


def apply_btn_click():
    # Log button click and update variables
    log("Button clicked: Apply")
    apply_config()


def save_config():
    log("Button clicked: Apply and save configuration")

    # Stop saving if validation fails
    if not apply_config():
        log("Configuration not saved due to validation error.")
        return

    # Create dictionary from current UI values including new mode elements
    new_config = {
        "SRC_DIR": src_dir_var.get(),
        "BACKUP_FOLDER": backup_folder_var.get(),
        "IMG_NAME": img_name_var.get(),
        "MONITOR_ROI": {
            "top": int(roi_top_var.get()),
            "left": int(roi_left_var.get()),
            "width": int(roi_width_var.get()),
            "height": int(roi_height_var.get()),
        },
        "SCREENSHOT_MODE": mode_var.get(),
        "SCREENSHOT_HOTKEY": hotkey_var.get(),
        "EXIT_HOTKEY": exit_hotkey_var.get(),
    }

    # Save to file and apply to memory
    with open(CONFIG_PATH, "w") as f:
        json.dump(new_config, f, indent=4)

    log("Configuration saved to file and applied in memory.")


def load_custom_config():
    # Open file dialog to select a config file
    filepath = filedialog.askopenfilename(
        initialdir=SCRIPT_DIR,
        title="Select Configuration File",
        filetypes=(
            ("Text files", "*.txt"),
            ("JSON files", "*.json"),
            ("All files", "*.*"),
        ),
    )

    # Stop execution if user canceled the dialog
    if not filepath:
        return

    try:
        # Read and parse the selected JSON file
        with open(filepath, "r") as f:
            new_config = json.load(f)

        # Update all StringVar variables with loaded data
        src_dir_var.set(new_config["SRC_DIR"])
        backup_folder_var.set(new_config["BACKUP_FOLDER"])
        img_name_var.set(new_config["IMG_NAME"])

        # Update ROI variables
        roi_top_var.set(str(new_config["MONITOR_ROI"]["top"]))
        roi_left_var.set(str(new_config["MONITOR_ROI"]["left"]))
        roi_width_var.set(str(new_config["MONITOR_ROI"]["width"]))
        roi_height_var.set(str(new_config["MONITOR_ROI"]["height"]))

        # Update mode and hotkeys variables
        mode_var.set(new_config["SCREENSHOT_MODE"])
        hotkey_var.set(new_config["SCREENSHOT_HOTKEY"])
        exit_hotkey_var.set(new_config["EXIT_HOTKEY"])

        # Reset button texts to normal state
        btn_rebind.config(text="Bind new hotkey", state="normal")
        btn_rebind_exit.config(text="Bind new hotkey", state="normal")

        # Apply loaded config to memory and log success
        apply_config()
        log(f"Custom configuration loaded from: {filepath}")

    except Exception as e:
        # Display error message if loading fails
        log(f"Error loading custom config: {e}")
        messagebox.showerror("Error", f"Failed to load configuration:\n{e}")


def save_custom_config():
    # Stop saving if configuration validation fails
    if not apply_config():
        return

    # Open file dialog to choose save destination
    filepath = filedialog.asksaveasfilename(
        initialdir=SCRIPT_DIR,
        title="Save Configuration As",
        defaultextension=".txt",
        filetypes=(
            ("Text files", "*.txt"),
            ("JSON files", "*.json"),
            ("All files", "*.*"),
        ),
    )

    # Stop execution if user canceled the dialog
    if not filepath:
        return

    # Create dictionary from current UI values
    new_config = {
        "SRC_DIR": src_dir_var.get(),
        "BACKUP_FOLDER": backup_folder_var.get(),
        "IMG_NAME": img_name_var.get(),
        "MONITOR_ROI": {
            "top": int(roi_top_var.get()),
            "left": int(roi_left_var.get()),
            "width": int(roi_width_var.get()),
            "height": int(roi_height_var.get()),
        },
        "SCREENSHOT_MODE": mode_var.get(),
        "SCREENSHOT_HOTKEY": hotkey_var.get(),
        "EXIT_HOTKEY": exit_hotkey_var.get(),
    }

    try:
        # Save the dictionary as a JSON file
        with open(filepath, "w") as f:
            json.dump(new_config, f, indent=4)

        # Log success after writing to file
        log(f"Custom configuration saved to: {filepath}")

    except Exception as e:
        # Display error message if saving fails
        log(f"Error saving custom config: {e}")
        messagebox.showerror("Error", f"Failed to save configuration:\n{e}")


def update_gui():
    global blink_toggle

    if not running:
        return

    lbl_last_backup_val.config(text=last_backup_time_str)

    if SCREENSHOT_MODE == "Hotkey":
        lbl_current_mode_val.config(text=f"Hotkey (Press '{SCREENSHOT_HOTKEY}')")
    else:
        lbl_current_mode_val.config(text="Automatic")

    if app_state == "IDLE":
        canvas_diode.itemconfig(diode_circle, fill="gray")
    elif app_state == "SUCCESS":
        canvas_diode.itemconfig(diode_circle, fill="green")
    elif app_state == "FAILED":
        canvas_diode.itemconfig(diode_circle, fill="red")
    elif app_state == "SCANNING":
        color = "orange" if blink_toggle else "yellow"
        canvas_diode.itemconfig(diode_circle, fill=color)
        blink_toggle = not blink_toggle

    root.after(1000, update_gui)


def browse_src_dir():
    log("Button clicked: Browse...")

    # Open dialog and ask for directory
    selected = filedialog.askdirectory()
    if selected:
        src_dir_var.set(selected)


def update_screenshot_hotkey_gui(key):
    hotkey_var.set(key)
    btn_rebind.config(text="Bind new hotkey", state="normal")


def listen_for_screenshot_hotkey():
    btn_rebind.config(text="Press any key...", state="disabled")
    root.focus()

    def wait_key():
        key = keyboard.read_key()
        root.after(0, update_screenshot_hotkey_gui, key)

    threading.Thread(target=wait_key, daemon=True).start()


def update_exit_hotkey_gui(key):
    exit_hotkey_var.set(key)
    btn_rebind_exit.config(text="Bind new hotkey", state="normal")


def listen_for_exit_hotkey():
    btn_rebind_exit.config(text="Press any key...", state="disabled")
    root.focus()

    def wait_key():
        key = keyboard.read_key()
        root.after(0, update_exit_hotkey_gui, key)

    threading.Thread(target=wait_key, daemon=True).start()


# Initialize GUI main window
root = tk.Tk()
root.title("SaveGuard")

# Set up notebook for tabs
notebook = ttk.Notebook(root)
notebook.pack(fill="both", expand=True, padx=10, pady=10)


# Remove focus from input fields whenever the user switches tabs
def clear_focus(event):
    root.focus()


notebook.bind("<<NotebookTabChanged>>", clear_focus)

# Create two frames for our tabs
tab_dashboard = ttk.Frame(notebook)
tab_settings = ttk.Frame(notebook)

# Add frames to notebook
notebook.add(tab_dashboard, text="Dashboard")
notebook.add(tab_settings, text="Settings")

# Define StringVars holding configuration values and explicitly bind them to root
src_dir_var = tk.StringVar(root, value=config["SRC_DIR"])
backup_folder_var = tk.StringVar(root, value=config["BACKUP_FOLDER"])
img_name_var = tk.StringVar(root, value=config["IMG_NAME"])
roi_top_var = tk.StringVar(root, value=str(config["MONITOR_ROI"]["top"]))
roi_left_var = tk.StringVar(root, value=str(config["MONITOR_ROI"]["left"]))
roi_width_var = tk.StringVar(root, value=str(config["MONITOR_ROI"]["width"]))
roi_height_var = tk.StringVar(root, value=str(config["MONITOR_ROI"]["height"]))
mode_var = tk.StringVar(root, value=config.get("SCREENSHOT_MODE", "Auto"))
hotkey_var = tk.StringVar(root, value=config.get("SCREENSHOT_HOTKEY", "]"))
exit_hotkey_var = tk.StringVar(root, value=config.get("EXIT_HOTKEY", "f10"))

# Auto-fallback to Hotkey mode if the template image is missing on startup
if mode_var.get() == "Auto" and not os.path.exists(IMG_PATH):
    log(f"Startup Warning: Image not found at {IMG_PATH}. Switching to Hotkey mode.")

    # Hide the main window temporarily to center the messagebox (optional but looks cleaner)
    root.withdraw()
    messagebox.showwarning(
        "Image Not Found",
        f"The configured image file was not found:\n{IMG_PATH}\n\nSwitching to 'Hotkey' mode automatically.",
    )
    root.deiconify()  # Restore the main window

    mode_var.set("Hotkey")
    SCREENSHOT_MODE = "Hotkey"

# --- TAB 1: DASHBOARD ---

# Create a container frame aligned to the top-left
dash_container = tk.Frame(tab_dashboard)
dash_container.pack(anchor="nw", padx=20, pady=20)

# Display last backup time
tk.Label(dash_container, text="Last Backup Time:", font=("Arial", 12)).grid(
    row=0, column=0, sticky="w", pady=10, padx=10
)
lbl_last_backup_val = tk.Label(dash_container, text="None", font=("Arial", 12, "bold"))
lbl_last_backup_val.grid(row=0, column=1, sticky="w", pady=10)

# Display screenshot status with diode
tk.Label(dash_container, text="Screenshot Status:", font=("Arial", 12)).grid(
    row=1, column=0, sticky="w", pady=10, padx=10
)
canvas_diode = tk.Canvas(dash_container, width=30, height=30)
canvas_diode.grid(row=1, column=1, sticky="w", pady=10)
diode_circle = canvas_diode.create_oval(5, 5, 25, 25, fill="gray")

# Display current mode and hotkey
tk.Label(dash_container, text="Current Mode:", font=("Arial", 12)).grid(
    row=2, column=0, sticky="w", pady=10, padx=10
)
lbl_current_mode_val = tk.Label(
    dash_container, text="Loading...", font=("Arial", 12, "bold")
)
lbl_current_mode_val.grid(row=2, column=1, sticky="w", pady=10)

# Legend for diode colors
legend_frame = tk.Frame(dash_container)
legend_frame.grid(row=3, column=0, columnspan=2, pady=20, padx=10, sticky="w")
tk.Label(legend_frame, text="Color Legend:", font=("Arial", 10, "bold")).pack(
    anchor="w"
)
tk.Label(legend_frame, text="Gray - Waiting for new save", fg="gray").pack(anchor="w")
tk.Label(legend_frame, text="Yellow/Orange - Scanning", fg="orange").pack(anchor="w")
tk.Label(legend_frame, text="Green - Success (screenshot taken)", fg="green").pack(
    anchor="w"
)
tk.Label(legend_frame, text="Red - Image not found", fg="red").pack(anchor="w")

# --- TAB 2: SETTINGS ---

# Setup source directory input and browse button
tk.Label(tab_settings, text="Source Directory:").grid(
    row=0, column=0, sticky="e", padx=5, pady=5
)
tk.Entry(tab_settings, textvariable=src_dir_var, width=50).grid(
    row=0, column=1, columnspan=3, padx=5
)
tk.Button(tab_settings, text="Browse...", command=browse_src_dir).grid(
    row=0, column=4, padx=5
)

# Setup backup folder and image name inputs
tk.Label(tab_settings, text="Backup Folder:").grid(
    row=1, column=0, sticky="e", padx=5, pady=5
)
tk.Entry(tab_settings, textvariable=backup_folder_var, width=50).grid(
    row=1, column=1, columnspan=3, padx=5
)

tk.Label(tab_settings, text="Image Name:").grid(
    row=2, column=0, sticky="e", padx=5, pady=5
)
tk.Entry(tab_settings, textvariable=img_name_var, width=50).grid(
    row=2, column=1, columnspan=3, padx=5
)

# Setup region of interest inputs
tk.Label(tab_settings, text="ROI Top:").grid(
    row=3, column=0, sticky="e", padx=5, pady=5
)
tk.Entry(tab_settings, textvariable=roi_top_var, width=10).grid(
    row=3, column=1, sticky="w"
)
tk.Label(tab_settings, text="ROI Left:").grid(row=3, column=2, sticky="e", padx=5)
tk.Entry(tab_settings, textvariable=roi_left_var, width=10).grid(
    row=3, column=3, sticky="w"
)

tk.Label(tab_settings, text="ROI Width:").grid(
    row=4, column=0, sticky="e", padx=5, pady=5
)
tk.Entry(tab_settings, textvariable=roi_width_var, width=10).grid(
    row=4, column=1, sticky="w"
)
tk.Label(tab_settings, text="ROI Height:").grid(row=4, column=2, sticky="e", padx=5)
tk.Entry(tab_settings, textvariable=roi_height_var, width=10).grid(
    row=4, column=3, sticky="w"
)

# ROI Explanation text
roi_info = (
    "ROI (Region of Interest) is the screen area where the script searches for the image.\n"
    "Top/Left are the coordinates from the top-left corner (0,0).\n"
    "Width/Height are the dimensions of the scanned area in pixels."
)
tk.Label(tab_settings, text=roi_info, justify="left", fg="gray").grid(
    row=5, column=0, columnspan=5, pady=10
)

# Screenshot Mode
tk.Label(tab_settings, text="Mode:").grid(row=6, column=0, sticky="e", padx=5, pady=5)
mode_frame = tk.Frame(tab_settings)
mode_frame.grid(row=6, column=1, columnspan=3, sticky="w")
tk.Radiobutton(mode_frame, text="Automatic", variable=mode_var, value="Auto").pack(
    side="left"
)
tk.Radiobutton(mode_frame, text="Hotkey", variable=mode_var, value="Hotkey").pack(
    side="left", padx=10
)

# Screenshot Hotkey Rebinding
tk.Label(tab_settings, text="Screenshot Hotkey:").grid(
    row=7, column=0, sticky="e", padx=5, pady=5
)
tk.Label(tab_settings, textvariable=hotkey_var, font=("Arial", 10, "bold")).grid(
    row=7, column=1, sticky="w"
)
btn_rebind = tk.Button(
    tab_settings, text="Bind new hotkey", command=listen_for_screenshot_hotkey, width=16
)
btn_rebind.grid(row=7, column=2, sticky="w")

# Exit App Hotkey Rebinding
tk.Label(tab_settings, text="Exit App Hotkey:").grid(
    row=8, column=0, sticky="e", padx=5, pady=5
)
tk.Label(tab_settings, textvariable=exit_hotkey_var, font=("Arial", 10, "bold")).grid(
    row=8, column=1, sticky="w"
)
btn_rebind_exit = tk.Button(
    tab_settings, text="Bind new hotkey", command=listen_for_exit_hotkey, width=16
)
btn_rebind_exit.grid(row=8, column=2, sticky="w")

# Setup action buttons at the bottom
button_frame = tk.Frame(tab_settings)
button_frame.grid(row=9, column=0, columnspan=5, pady=20)

# Top row: Load and Export custom configs
top_btn_frame = tk.Frame(button_frame)
top_btn_frame.pack(side="top", pady=5)
tk.Button(top_btn_frame, text="Load Config...", command=load_custom_config).pack(
    side="left", padx=10
)
tk.Button(top_btn_frame, text="Export Config As...", command=save_custom_config).pack(
    side="left", padx=10
)

# Bottom row: Apply and Save to default config.txt
bot_btn_frame = tk.Frame(button_frame)
bot_btn_frame.pack(side="top", pady=5)
tk.Button(
    bot_btn_frame, text="Apply (Memory only)", command=apply_btn_click, bg="lightgreen"
).pack(side="left", padx=10)
tk.Button(
    bot_btn_frame,
    text="Apply and save as default",
    command=save_config,
    bg="lightblue",
).pack(side="left", padx=10)

# Initial bind for exit hotkey
current_exit_hook = keyboard.add_hotkey(EXIT_HOTKEY, stop_all)

# Initial bind for manual screenshot hotkey
current_hotkey_hook = keyboard.add_hotkey(SCREENSHOT_HOTKEY, manual_screenshot_callback)

# Bind GUI close button and terminal interrupt
root.protocol("WM_DELETE_WINDOW", stop_all)
signal.signal(signal.SIGINT, stop_all)

# Start background worker threads
threading.Thread(target=backup_task, daemon=True).start()
threading.Thread(target=image_task, daemon=True).start()

# Start the continuous UI loop for updates
root.after(1000, update_gui)
root.mainloop()
