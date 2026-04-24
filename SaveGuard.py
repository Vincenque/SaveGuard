# SaveGuard.py
import os
import time
import shutil
import threading
import cv2
import numpy as np
import keyboard
import json
import tkinter as tk
from tkinter import filedialog, ttk
from mss import mss
from datetime import datetime
import sys
import signal

# Determine script directory and load config
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.txt")

with open(CONFIG_PATH, "r") as f:
    config = json.load(f)

# Setup log directory and log file name at the top
LOGS_DIR = os.path.join(SCRIPT_DIR, "Logs")
os.makedirs(LOGS_DIR, exist_ok=True)
startup_time = datetime.now().strftime("%Y-%m-%d--%H-%M-%S")
LOG_FILE = os.path.join(LOGS_DIR, f"{startup_time}_Log.txt")

# Global variables loaded from config
SRC_DIR = config["SRC_DIR"]
DST_DIR = os.path.join(SCRIPT_DIR, config["BACKUP_FOLDER"])
IMG_PATH = os.path.join(SCRIPT_DIR, config["IMG_NAME"])
MONITOR_ROI = config["MONITOR_ROI"]

running = True
trigger_correlation = threading.Event()

# Global variables for GUI state updates
last_backup_time_str = "None"
app_state = "IDLE"  # States: IDLE, SCANNING, SUCCESS
blink_toggle = False


def log(msg):
    # Generate timestamp string
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    full_msg = f"[{timestamp}] {msg}"

    # Print to console and append to log file
    print(full_msg)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(full_msg + "\n")


def stop_all(*args):
    global running
    log("Terminating all tasks and closing...")

    # Trigger events to unblock loops
    running = False
    trigger_correlation.set()

    # Destroy UI and kill process completely
    root.destroy()
    sys.exit(0)


def backup_task():
    global last_backup_time_str
    os.makedirs(DST_DIR, exist_ok=True)

    while running:
        for f in os.listdir(SRC_DIR):
            path = os.path.join(SRC_DIR, f)

            # Check if it is a file and process it regardless of its extension or name
            if os.path.isfile(path):
                mtime = os.path.getmtime(path)

                date_str = datetime.fromtimestamp(mtime).strftime("%Y%m%d_%H%M%S")
                target_path = os.path.join(DST_DIR, f"{date_str}_{f}")

                if not os.path.exists(target_path):
                    shutil.copy2(path, target_path)
                    log(f"Backed up: {f}. Triggering image correlation.")

                    # Update GUI string with exact HH:MM:SS format
                    last_backup_time_str = datetime.now().strftime("%H:%M:%S")
                    trigger_correlation.set()

        time.sleep(1)


def image_task():
    global app_state
    sct = mss()

    while running:
        if not trigger_correlation.is_set():
            trigger_correlation.wait(timeout=1.0)
            continue

        # Load image dynamically inside the loop to apply changes immediately
        log("New backup detected. Starting correlation scan...")
        app_state = "SCANNING"
        template = cv2.imread(IMG_PATH, cv2.IMREAD_GRAYSCALE)

        while trigger_correlation.is_set() and running:
            screen = np.array(sct.grab(MONITOR_ROI))
            gray = cv2.cvtColor(screen, cv2.COLOR_BGRA2GRAY)

            res = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(res)
            log(f"Current image correlation: {max_val * 100:.2f}%")

            if max_val > 0.9:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                screenshot_path = os.path.join(DST_DIR, f"{ts}_Screenshot.png")

                sct.shot(mon=2, output=screenshot_path)
                log(f"Threshold reached! Screenshot saved: {screenshot_path}")

                # Turn diode green and wait for next trigger
                app_state = "SUCCESS"
                trigger_correlation.clear()

            time.sleep(1)


def apply_config():
    global SRC_DIR, DST_DIR, IMG_PATH, MONITOR_ROI

    # Apply new GUI values to global memory variables
    SRC_DIR = src_dir_var.get()
    DST_DIR = os.path.join(SCRIPT_DIR, backup_folder_var.get())
    IMG_PATH = os.path.join(SCRIPT_DIR, img_name_var.get())
    MONITOR_ROI = {
        "top": int(roi_top_var.get()),
        "left": int(roi_left_var.get()),
        "width": int(roi_width_var.get()),
        "height": int(roi_height_var.get()),
    }


def apply_btn_click():
    # Log button click and update variables
    log("Button clicked: Apply")
    apply_config()


def save_config():
    log("Button clicked: Apply and save configuration")

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
    }

    # Save to file and apply to memory
    with open(CONFIG_PATH, "w") as f:
        json.dump(new_config, f, indent=4)

    apply_config()
    log("Configuration saved to file and applied in memory.")


def update_gui():
    global blink_toggle

    lbl_last_backup_val.config(text=last_backup_time_str)

    if app_state == "IDLE":
        canvas_diode.itemconfig(diode_circle, fill="gray")
    elif app_state == "SUCCESS":
        canvas_diode.itemconfig(diode_circle, fill="green")
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


# Initialize GUI main window
root = tk.Tk()
root.title("SaveGuard")

# Set up notebook for tabs
notebook = ttk.Notebook(root)
notebook.pack(fill="both", expand=True, padx=10, pady=10)

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

# --- TAB 1: DASHBOARD ---

# Create a container frame that expands to center contents
dash_container = tk.Frame(tab_dashboard)
dash_container.pack(expand=True)

# Display last backup time
tk.Label(dash_container, text="Last Backup Time:", font=("Arial", 12)).grid(
    row=0, column=0, sticky="e", pady=10, padx=10
)
lbl_last_backup_val = tk.Label(dash_container, text="None", font=("Arial", 12, "bold"))
lbl_last_backup_val.grid(row=0, column=1, sticky="w", pady=10)

# Display screenshot status with diode
tk.Label(dash_container, text="Screenshot Status:", font=("Arial", 12)).grid(
    row=1, column=0, sticky="e", pady=10, padx=10
)
canvas_diode = tk.Canvas(dash_container, width=30, height=30)
canvas_diode.grid(row=1, column=1, sticky="w", pady=10)
diode_circle = canvas_diode.create_oval(5, 5, 25, 25, fill="gray")

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

# Setup action buttons at the bottom
button_frame = tk.Frame(tab_settings)
button_frame.grid(row=5, column=0, columnspan=5, pady=20)

# Apply button (memory only) and Save button (memory + file)
tk.Button(button_frame, text="Apply", command=apply_btn_click, bg="lightgreen").pack(
    side="left", padx=10
)
tk.Button(
    button_frame,
    text="Apply and save configuration",
    command=save_config,
    bg="lightblue",
).pack(side="left", padx=10)

# Bind F10 hotkey
keyboard.add_hotkey("f10", stop_all)

# Bind GUI close button and terminal interrupt
root.protocol("WM_DELETE_WINDOW", stop_all)
signal.signal(signal.SIGINT, stop_all)

# Start background worker threads
threading.Thread(target=backup_task, daemon=True).start()
threading.Thread(target=image_task, daemon=True).start()

# Start the continuous UI loop for updates
root.after(1000, update_gui)
root.mainloop()
