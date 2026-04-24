import os
import time
import shutil
import threading
import cv2
import numpy as np
import keyboard
import json
from mss import mss
from datetime import datetime

# Determine the absolute path of the directory containing this script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Read configuration from a JSON-formatted text file
with open(os.path.join(SCRIPT_DIR, "config.txt"), "r") as f:
    config = json.load(f)

# Assign configuration values to constants
SRC_DIR = config["SRC_DIR"]
DST_DIR = os.path.join(SCRIPT_DIR, config["BACKUP_FOLDER"])
IMG_PATH = os.path.join(SCRIPT_DIR, config["IMG_NAME"])
MONITOR_ROI = config["MONITOR_ROI"]

running = True
trigger_correlation = threading.Event()


def log(msg):
    # Print message with current timestamp as requested
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")


def stop_all():
    global running
    log("F10 pressed. Terminating all tasks...")
    running = False
    # Set event to unblock any waiting threads
    trigger_correlation.set()


def backup_task():
    os.makedirs(DST_DIR, exist_ok=True)

    while running:
        # Iterate through all files in the source directory
        for f in os.listdir(SRC_DIR):
            path = os.path.join(SRC_DIR, f)
            mtime = os.path.getmtime(path)

            date_str = datetime.fromtimestamp(mtime).strftime("%Y%m%d_%H%M%S")
            target_path = os.path.join(DST_DIR, f"{date_str}_{f}")

            # Copy file if it hasn't been backed up yet
            if not os.path.exists(target_path):
                shutil.copy2(path, target_path)
                log(f"Backed up: {f}. Triggering image correlation.")
                trigger_correlation.set()

        time.sleep(1)


def image_task():
    template = cv2.imread(IMG_PATH, cv2.IMREAD_GRAYSCALE)
    sct = mss()

    while running:
        if not trigger_correlation.is_set():
            trigger_correlation.wait(timeout=1.0)
            continue

        log("New backup detected. Starting correlation scan...")

        while trigger_correlation.is_set() and running:
            # Grab the screen area and convert to grayscale
            screen = np.array(sct.grab(MONITOR_ROI))
            gray = cv2.cvtColor(screen, cv2.COLOR_BGRA2GRAY)

            res = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(res)
            log(f"Current image correlation: {max_val * 100:.2f}%")

            # Take screenshot on high correlation match
            if max_val > 0.9:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                screenshot_path = os.path.join(DST_DIR, f"{ts}_Screenshot.png")

                sct.shot(mon=2, output=screenshot_path)
                log(f"Threshold reached! Screenshot saved: {screenshot_path}")
                trigger_correlation.clear()

            time.sleep(1)


# Register hotkey for stopping the script
keyboard.add_hotkey("f10", stop_all)

# Initialize threads for backup and image monitoring
backup_thread = threading.Thread(target=backup_task)
image_thread = threading.Thread(target=image_task)

backup_thread.start()
image_thread.start()

# Keep the main thread alive while tasks are running
while running:
    time.sleep(0.1)
