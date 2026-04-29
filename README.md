# SaveGuard - Universal Game Save Backuper with Visual Indexing



**SaveGuard** is a smart tool for automatically backing up game saves, enhanced with a "visual indexing" system. The application not only secures your progress files but also takes a screenshot at the moment of saving, allowing you to easily identify the game stage associated with a specific backup.



## 🚀 How it works



The application runs in the background and monitors a specified game save folder. The process consists of three steps:

1. **Monitoring:** When a new file (or a file with a new modification date) appears in the source folder, the app immediately copies it to a secure location with a unique timestamp.

2. **Context Verification / Waiting:** After the backup is made, the app enters a screenshot waiting state based on your chosen mode:
    * **Automatic Mode:** The app continuously searches the screen for a specific, characteristic image snippet (e.g., a quest log header).
    * **Hotkey Mode:** The app simply waits for you to press a designated keyboard shortcut.

3. **Visual Index:** If the unique snippet is detected (Auto mode) or you press the hotkey (Hotkey mode), the app takes a full screenshot. As a result, right next to your save file in the backup folder, you get an image showing exactly what you were doing in the game at that time.



## 📦 Installation & Usage



**Option 1: Standalone Executable (Recommended)**

1. Go to the **Releases** tab on GitHub.

2. Download the latest executable file.

3. Run the application. No installation is required.



**Option 2: Running from source via Python IDLE**

1. Clone the repository or download the `SaveGuard.py` file.

2. Ensure you have Python installed (tested on `3.14.4`).

3. Right-click the `SaveGuard.py` file and select **Edit with IDLE**.

4. Once the IDLE editor opens, press **F5** or select **Run -> Run Module** from the top menu to execute the script.

5. On the first run, the script will automatically create a `Logs` folder and install the necessary libraries (`opencv-python`, `mss`, `numpy`, `keyboard`).



## ⚙️ Configuration (Settings)



The application features a user-friendly graphical interface divided into tabs:



### Dashboard

* **Last Backup Time:** Displays the exact time of the last successful backup operation.

* **Screenshot Status:** A colored indicator showing the status of the image correlation:

&#x20;   * `Gray` - Waiting for a new save.

&#x20;   * `Yellow/Orange` - Scanning the screen.

&#x20;   * `Green` - Success (image found, screenshot taken).

&#x20;   * `Red` - Error (image not found on screen or the template file does not exist).



### Settings

* **Source Directory:** The folder where the game stores its saves.

* **Backup Folder:** The folder where backups and screenshots will be stored.

* **Image Name:** The name of a small `.png` file (template) that the app should look for on the screen.

* **ROI (Region of Interest):** Allows you to limit the screen scanning to a specific area (e.g., top-left corner), which drastically increases performance and accuracy.
* **Mode:** Choose between "Automatic" (scans for the image) or "Hotkey" (waits for a manual key press).
* **Current Hotkey:** Displays the currently bound key for manual screenshots. Click "Bind new hotkey" to change it.



## ⌨️ Controls

* **F10:** Safely terminates all background processes and closes the application immediately.

* **Apply:** Applies the settings changes to the current session only.

* **Apply and save configuration:** Saves the settings to `config.txt` so they are available after a restart.



---

*Built for gamers who want full control over their adventure history.*

