# Gamana (Pragati AI Smart Traffic System)

Welcome to **Gamana** (Pragati AI), a highly intelligent, real-time traffic management system. The core objective of Gamana is to eliminate the inefficiencies of traditional, static traffic light timers. By utilizing advanced computer vision and predictive analytics, Gamana dynamically adapts traffic signals based on actual vehicular density, lane pressure, and observed congestion in real-time.

---

## 🚀 Key Features

- **Real-Time Vehicle Detection & Tracking**: Utilizes **YOLOv8** (You Only Look Once) to identify vehicles on video feeds with pinpoint accuracy, coupled with a custom motion tracker for maintaining persistent vehicle IDs across frames.
- **Dynamic Lane Pressure Analysis**: Automatically measures the "pressure" of each lane by analyzing the number of moving vs. stationary vehicles and their respective wait times.
- **Intelligent Signal Controller**: Calculates optimal green light durations on the fly. Lanes with the highest pressure and longest wait times are prioritized seamlessly.
- **Predictive Traffic Modeling**: Smooths out historical traffic data to accurately predict upcoming congestion spikes, adjusting signal behaviors *before* severe traffic jams occur.
- **Real-Time Dashboard**: A sleek, modern **React** frontend that visualizes the current simulation, including live video feeds, lane geometries, pressure charts, and exactly what decisions the AI is making in real-time.

---

## 🏗️ Architecture Stack

- **Backend**: Python 3.8+, OpenCV (Computer Vision pipelines), PyTorch / Ultralytics YOLOv8 (Inference Engine), Flask & Flask-SocketIO (API & real-time WebSocket communication).
- **Frontend**: React, Vite, tailwindcss (or standard CSS modules), providing an interactive, blazing-fast user interface.

---

## 🛠️ Detailed Setup & Execution Guide

To get Gamana up and running, you need to run both the **Backend AI Server** and the **Frontend Dashboard** simultaneously in two separate terminal windows.

### Prerequisites
- **Python 3.8+** installed on your system.
- **Node.js** (v16+) installed for frontend compilation.

---

### Step 1: Running the Backend

The backend handles all heavy lifting: video frame processing, running the YOLOv8 model, executing the signal control logic, and streaming the visualized state to the dashboard. 

This project is configured to use a local Python virtual environment (`venv`) to ensure dependencies do not conflict with your global system.

1. **Open a terminal** and navigate to the project root directory:
   ```bash
   cd path/to/gamana
   ```

2. **Navigate to the backend folder**:
   ```bash
   cd backend
   ```

3. **Install Dependencies** (Only required if you haven't already):
   *Ensure you are using the virtual environment's python/pip!*
   ```bash
   ..\venv\Scripts\python.exe -m pip install -r requirements.txt
   ```
   *(Note: For Mac/Linux users, this would be `../venv/bin/python -m pip install -r requirements.txt`)*

4. **Start the AI Processing Server**:
   You can start the backend by running `main.py` using the virtual environment interpreter and pointing it to a video source.
   ```bash
   ..\venv\Scripts\python.exe main.py --source intersection.mp4
   ```
   **Alternative Sources:**
   - Use a different video file: `--source your_video_file.mp4`
   - Use your physical webcam: `--source 0`
   - Run without a pop-up OpenCV window (Headless mode): Add `--no-display`

By default, the backend will now be analyzing the video and broadcasting data via SocketIO on **Port 5000**.

---

### Step 2: Running the Frontend

The frontend receives the real-time data from the backend and renders the interactive dashboard UI.

1. **Open a SECOND terminal window** and navigate to the project root directory.

2. **Navigate to the frontend folder**:
   ```bash
   cd frontend
   ```

3. **Install Node Packages** (Only required the very first time):
   ```bash
   npm install
   ```

4. **Start the Development Server**:
   ```bash
   npm run dev
   ```

The Vite development server will start up rapidly.

### Step 3: View the Dashboard!

Once both the backend and frontend are running:
1. Open your favorite web browser.
2. Navigate to **[http://localhost:5173](http://localhost:5173)** (or whichever port Vite assigned in the terminal).
3. You will immediately see the live traffic analysis and the AI actively managing the signal controllers!

---

## 🤝 Troubleshooting

- **`ModuleNotFoundError` on Backend**: This happens if you try to run `python main.py` using your system python rather than the environment included in `gamana/venv`. Always use `..\venv\Scripts\python.exe` or activate the virtual environment first.
- **`Cannot open source: video.mp4`**: If your video file is located inside a OneDrive synced folder, it might be a "Cloud-only" placeholder. Open the file normally via File Explorer first to force Windows to download it to your physical disk.
- **Port In Use (5000 / 5173)**: Ensure no other applications (like another Flask app or Node server) are currently holding the ports open.
