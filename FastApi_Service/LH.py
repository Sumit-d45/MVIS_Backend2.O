
"""
# # # # H2932340, H2681530
Dual Camera Machine Vision System with Frame ID Tracking, Excel Logging, and ROI Detection
"""
import PySpin
import cv2
import time
import os
import json
import numpy as np
import threading
import pandas as pd
from datetime import datetime
from queue import Queue, Empty
from collections import OrderedDict
import openpyxl
from pathlib import Path

# ============================================
# DUAL CAMERA CONFIGURATION
# ============================================

# Camera 1 configuration (BV camera with ROI tracking)
CAMERA1_CONFIG = {
    "serial": "22317355",       # BV Camera (Mono8)
    "display_name": "LH_BV",
    "output_folder": r"D:\MVC_BV_LH",
    "output_folder_raw": r"D:\MVC_BV_LH_RAW",  # After 6PM folder
    "display_window": "Camera 1: LH_BV (ROI Tracking)",
    "pixel_format": "Mono8",
    "resolution": (1920, 1120),  # BV camera resolution
    "has_roi_tracking": True,    # This camera handles ROI tracking
    "x_offset": 0,               # X offset for saved images (0 = no offset)
    "y_offset": 0,               # Y offset for saved images (0 = no offset)
    # Gain and Exposure settings for different times
    "gain_morning": 3.0,        # Gain for morning (8AM) - Will set later
    "gain_evening": 2.3,        # Gain for evening (6PM) - Will set later
    "exposure_morning": 260.0,    # Exposure for morning (8AM) in microseconds - Will set later
    "exposure_evening": 500.0     # Exposure for evening (6PM) in microseconds - Will set later
}

# Camera 2 configuration (Synchronized camera - SV)
CAMERA2_CONFIG = {
    "serial": "24203546",       # Second camera serial
    "display_name": "LH_SV",
    "output_folder": r"D:\MVC_SV_LH",
    "output_folder_raw": r"D:\MVC_SV_LH",  # After 6PM folder
    "display_window": "Camera 2: LH_SV (Synchronized)",
    "pixel_format": "BayerRG8",
    "resolution": (1648, 1536),  # SV camera resolution
    "has_roi_tracking": False,   # This camera follows Camera 1
    "x_offset": 0,               # X offset for saved images (0 = no offset)
    "y_offset": 0,               # Y offset for saved images (0 = no offset)
    # Gain and Exposure settings for different times
    "gain_morning": 12.0,        # Gain for morning (8AM) - Will set later
    "gain_evening": 15.0,        # Gain for evening (6PM) - Will set later
    "exposure_morning": 390.0,    # Exposure for morning (8AM) in microseconds - Will set later
    "exposure_evening": 1590.0     # Exposure for evening (6PM) in microseconds - Will set later
}

# List of all cameras
CAMERA_CONFIGS = [CAMERA1_CONFIG, CAMERA2_CONFIG]

# Network configuration
FORCE_IP_CONFIG = False
DESIRED_IP = "192.168.2.111"
DESIRED_SUBNET = "255.255.255.0"
DESIRED_GATEWAY = "192.168.2.1"

# JSON configuration file paths
TRAIN_ID_JSON_PATH = r"C:\Trigger\TrainId.json"
TRAIN_START_JSON_PATH = r"C:\Trigger\TrainStart.json"
# TRAIN_START_JSON_PATH = r"C:\WPMS_MVIS\config\TrainStart.json"
# TRAIN_ID_JSON_PATH = r"C:\WPMS_MVIS\config\TrainId.json"
CAPTURE_END_JSON_PATH = r"C:\Trigger\CaptureImageEnd.json"

# Time-based configuration
MORNING_HOUR = 7   # 8 AM
EVENING_HOUR = 17  # 6 PM

# ROI configurations (only for Camera 1)
ROI_CONFIGS = [
    {
        "name": "Left Bottom ROI",
        "coords": (0.0, 0.35, 0.5, 0.90),  # x1, y1, x2, y2 (relative)
        "reference_update_frames": 30,      # Frames to establish reference
        "match_threshold": 0.92,           # Similarity threshold (0-1)
        "stability_frames": 5,             # Consecutive frames for state change
        "reference_image": None,           # Will be set dynamically
        "match_history": [],                # Store match results
        "is_clear": False,                  # Current clear state
        "clear_count": 0,                   # Consecutive clear frames count
        "reference_ready": False,           # Reference image ready flag
        "frame_counter": 0                  # Counter for reference update
    },
    {
        "name": "Right Bottom ROI",
        "coords": (0.45, 0.35, 1.0, 0.90),
        "reference_update_frames": 30,
        "match_threshold": 0.85,
        "stability_frames": 5,
        "reference_image": None,
        "match_history": [],
        "is_clear": False,
        "clear_count": 0,
        "reference_ready": False,
        "frame_counter": 0
    }
]

# Image saving settings
IMAGE_QUALITY = 95
IMAGE_FORMAT = ".jpg"
IMAGE_PREFIX = "img"
LOG_FILENAME = "frame_log.xlsx"

# Frame skipping configuration - Save 1 frame, skip 2 frames
SKIP_PATTERN = [True, True, True]  # True = save, False = skip (Save 1, Skip 2)

# Status check interval (5 minutes in seconds)
STATUS_CHECK_INTERVAL = 300

# ROI Tracking settings (Camera 1 only)
ROI_LOCK_DELAY = 5  # seconds to lock ROI after train start
MIN_ROI_MATCH_SCORE = 0.96  # 85% similarity threshold
CLEAR_TARGET_DURATION = 20  # seconds of clear target before ending capture
MAX_MATCH_HISTORY = 30  # Number of frames to keep in match history

# Manual capture settings
MANUAL_CAPTURE_PREFIX = ""  

# TrainStart false duration to end capture (when ROIs don't get 30s clear)
TRAIN_START_FALSE_DURATION = 5  # seconds of TrainStart=FALSE to end capture

# COOLDOWN PERIOD SETTINGS
COOLDOWN_PERIOD = 20  # seconds to wait after capture end

# QUEUE SETTINGS FOR PRODUCER-CONSUMER ARCHITECTURE
FRAME_QUEUE_SIZE = 500  # Single queue per camera

# PySpin buffer settings
PYSPIN_BUFFER_COUNT = 200  # Increased from default
GET_NEXT_IMAGE_TIMEOUT = 2000  # Increased timeout in milliseconds

# FPS STABILIZATION SETTINGS
TARGET_FPS = 12.0  # Reduced to match typical write speed
FRAME_INTERVAL = 1.0 / TARGET_FPS  # 100ms per frame
FPS_TOLERANCE = 0.1  # Allow small fluctuations

# ============================================
# FRAME DATA CLASS
# ============================================

class FrameData:
    """Class to hold frame data with metadata"""
    __slots__ = ['frame', 'frame_id', 'sequence_number', 'pattern_index', 
                 'timestamp_string', 'camera_name', 'filename']
    
    def __init__(self, frame, frame_id, sequence_number, pattern_index, 
                 timestamp_string, camera_name):
        self.frame = frame
        self.frame_id = frame_id
        self.sequence_number = sequence_number
        self.pattern_index = pattern_index
        self.timestamp_string = timestamp_string
        self.camera_name = camera_name
        self.filename = None  # Will be set when saved

# ============================================
# EXCEL LOGGER CLASS
# ============================================

class ExcelLogger:
    """Thread-safe Excel logger for frame logging"""
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.log_lock = threading.Lock()
        self.log_data = []
        self.current_session_id = None
        self.log_file_path = None
    
    def start_session(self, session_id, output_folder):
        """Start a new logging session"""
        with self.log_lock:
            self.current_session_id = session_id
            self.log_data = []
            self.log_file_path = os.path.join(output_folder, LOG_FILENAME)
    
    def log_frame(self, frame_id, timestamp, camera_name, sequence_number, filename):
        """Log a frame to the Excel file"""
        with self.log_lock:
            self.log_data.append({
                'Frame ID': frame_id,
                'Timestamp': timestamp,
                'Camera Name': camera_name,
                'Sequence Number': sequence_number,
                'Saved Filename': filename,
                'Session ID': self.current_session_id
            })
    
    def save_log(self):
        """Save the log data to Excel file"""
        if not self.log_data or not self.log_file_path:
            return
        
        with self.log_lock:
            try:
                df = pd.DataFrame(self.log_data)
                
                # Reorder columns
                columns = ['Frame ID', 'Timestamp', 'Camera Name', 
                          'Sequence Number', 'Saved Filename', 'Session ID']
                df = df[columns]
                
                # Sort by Frame ID to ensure order
                df = df.sort_values('Frame ID')
                
                # Save to Excel
                df.to_excel(self.log_file_path, index=False, engine='openpyxl')
                
                print(f"  [LOG] Frame log saved to: {self.log_file_path}")
                print(f"  [LOG] Total frames logged: {len(self.log_data)}")
                
            except Exception as e:
                print(f"  [ERROR] Failed to save frame log: {e}")

# Initialize global Excel logger
excel_logger = ExcelLogger()

# ============================================
# GLOBAL VARIABLES
# ============================================

# Save control variables
save_frames = False
camera1_save_active = False
camera2_save_active = False
roi_tracking_active = False  # ROI tracking active (Camera 1 only)
capture_end_triggered = False
all_rois_clear = False

# Capture modes
capture_mode = "AUTO"  # "AUTO" or "MANUAL"
manual_capture_active = False

# ID and folder management
current_train_id = ""
camera1_output_folder_path = ""
camera2_output_folder_path = ""

# Frame counters - SIMPLE SEQUENTIAL COUNTERS
camera1_frame_counter = 0
camera2_frame_counter = 0
camera1_image_counter = 0
camera2_image_counter = 0

# Frame ID counters (sequential across all captures)
camera1_frame_id_counter = 0
camera2_frame_id_counter = 0

# Skip pattern indices for each camera
camera1_skip_pattern_index = 0
camera2_skip_pattern_index = 0

# Thread-safe queues for producer-consumer pattern
camera1_frame_queue = Queue(maxsize=FRAME_QUEUE_SIZE)
camera2_frame_queue = Queue(maxsize=FRAME_QUEUE_SIZE)

# Threading and synchronization
camera1_lock = threading.Lock()
camera2_lock = threading.Lock()
roi_lock = threading.Lock()
manual_lock = threading.Lock()
camera1_frame = None
camera2_frame = None
camera1_ready = False
camera2_ready = False
camera1_object = None
camera2_object = None
stop_threads = False
stop_saver_threads = False

# PySpin system
system = None
camera_list = None

# Status tracking
last_status_check_time = time.time()
last_save_notification = 0
save_notification_interval = 60

# Session management
session_active = False
session_start_time = None
session_frame_counter = 0  # Global frame counter across both cameras

# FPS calculation
camera1_fps_counter = 0
camera2_fps_counter = 0
camera1_fps_timer = time.time()
camera2_fps_timer = time.time()
camera1_current_fps = 0
camera2_current_fps = 0
camera1_current_fps_display = 0
camera2_current_fps_display = 0

# Frame timing for FPS stabilization
camera1_last_frame_time = 0
camera2_last_frame_time = 0
camera1_frame_times = []
camera2_frame_times = []
MAX_FRAME_TIME_HISTORY = 30

# Display windows
display_windows_created = False

# ROI tracking (Camera 1 only)
roi_reference_locked = False
roi_lock_timer = None
target_clear_start_time = None
roi_frame_counter = 0
train_start_true_time = None

# TrainStart state tracking
train_start_state = False
train_start_false_start_time = None

# Cooldown tracking
cooldown_active = False
cooldown_start_time = None

# Time-based configuration
current_time_based_config = "MORNING"
last_time_check = time.time()
time_check_interval = 60

# ============================================
# UTILITY FUNCTIONS
# ============================================

def get_current_time_based_config():
    """Determine current time period (MORNING or EVENING)"""
    current_hour = datetime.now().hour
    
    if current_hour >= EVENING_HOUR or current_hour < MORNING_HOUR:
        return "EVENING"
    else:
        return "MORNING"

def get_output_folder_for_camera(camera_config, manual_mode=False, train_id=""):
    """Get appropriate output folder based on time of day"""
    time_period = get_current_time_based_config()
    
    if manual_mode:
        folder_name = f"{MANUAL_CAPTURE_PREFIX}{train_id}"
    else:
        folder_name = train_id
    
    if time_period == "EVENING":
        base_folder = camera_config["output_folder_raw"]
    else:
        base_folder = camera_config["output_folder"]
    
    return os.path.join(base_folder, folder_name)

def apply_camera_settings_based_on_time(cam, camera_config):
    """Apply gain and exposure settings based on current time"""
    try:
        time_period = get_current_time_based_config()
        
        if time_period == "EVENING":
            gain_value = camera_config["gain_evening"]
            exposure_value = camera_config["exposure_evening"]
            period_name = "EVENING"
        else:
            gain_value = camera_config["gain_morning"]
            exposure_value = camera_config["exposure_morning"]
            period_name = "MORNING"
        
        # Apply gain if set and available
        if gain_value > 0:
            try:
                if PySpin.IsAvailable(cam.Gain) and PySpin.IsWritable(cam.Gain):
                    cam.Gain.SetValue(gain_value)
                    print(f"  {camera_config['display_name']}: Applied {period_name} gain: {gain_value}")
            except Exception as e:
                print(f"  Warning: Could not set gain for {camera_config['display_name']}: {e}")
        
        # Apply exposure if set and available
        if exposure_value > 0:
            try:
                if PySpin.IsAvailable(cam.ExposureTime) and PySpin.IsWritable(cam.ExposureTime):
                    if PySpin.IsAvailable(cam.ExposureAuto):
                        cam.ExposureAuto.SetValue(PySpin.ExposureAuto_Off)
                    cam.ExposureTime.SetValue(exposure_value)
                    print(f"  {camera_config['display_name']}: Applied {period_name} exposure: {exposure_value} µs")
            except Exception as e:
                print(f"  Warning: Could not set exposure for {camera_config['display_name']}: {e}")
        
        return True
    except Exception as e:
        print(f"  Error applying time-based settings for {camera_config['display_name']}: {e}")
        return False

def get_timestamp_string():
    """Get current timestamp in format: HH_MM_SS_milli_micro (first 5 digits of microseconds)"""
    now = datetime.now()
    milliseconds = int(now.microsecond / 1000)
    microseconds = now.microsecond
    
    timestamp = f"{now.hour:02d}_{now.minute:02d}_{now.second:02d}_{milliseconds:03d}_{microseconds:05d}"
    return timestamp

def get_filename_from_sequence(camera_index, frame_id, sequence_number, timestamp_string):
    """Generate filename using frame_id and sequence number"""
    return f"{IMAGE_PREFIX}{sequence_number:04d}_{timestamp_string}{IMAGE_FORMAT}"

def apply_offset_to_frame(frame, x_offset, y_offset):
    """Apply X and Y offset to frame by shifting and cropping"""
    if x_offset == 0 and y_offset == 0:
        return frame
    
    height, width = frame.shape[:2]
    translation_matrix = np.float32([[1, 0, x_offset], [0, 1, y_offset]])
    shifted_frame = cv2.warpAffine(frame, translation_matrix, (width, height))
    return shifted_frame

def check_train_start():
    """Check if we should start saving frames based on TrainStart.json"""
    try:
        with open(TRAIN_START_JSON_PATH, 'r') as file:
            data = json.load(file)
            if "trainStart" in data:
                return data.get("trainStart", False)
            elif "TrainStart" in data:
                return data.get("TrainStart", False)
            else:
                return False
    except FileNotFoundError:
        print(f"ERROR: TrainStart.json not found at {TRAIN_START_JSON_PATH}")
        return False
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in TrainStart.json: {e}")
        return False
    except Exception as e:
        print(f"ERROR reading TrainStart.json: {e}")
        return False

def get_train_id():
    """Get the current train ID from TrainId.json"""
    try:
        with open(TRAIN_ID_JSON_PATH, 'r') as file:
            data = json.load(file)
            if "trainId" in data:
                train_id = data.get("trainId", "")
            elif "TrainId" in data:
                train_id = data.get("TrainId", "")
            else:
                return ""
            return str(train_id).strip()
    except FileNotFoundError:
        print(f"ERROR: TrainId.json not found at {TRAIN_ID_JSON_PATH}")
        return ""
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in TrainId.json: {e}")
        return ""
    except Exception as e:
        print(f"ERROR reading TrainId.json: {e}")
        return ""

def update_capture_end_json(is_capturing, clear_time=None, manual_mode=False, reason=""):
    """Update CaptureImageEnd.json file with ROI clear status"""
    global capture_end_triggered
    
    try:
        data = {}
        if os.path.exists(CAPTURE_END_JSON_PATH):
            with open(CAPTURE_END_JSON_PATH, 'r') as file:
                try:
                    data = json.load(file)
                except json.JSONDecodeError:
                    data = {}
        
        data["CaptureImageEnd"] = not is_capturing
        data["CameraName"] = "DUAL_CAMERA_SYSTEM"
        data["CameraSerials"] = f"{CAMERA1_CONFIG['serial']}, {CAMERA2_CONFIG['serial']}"
        data["ROICamera"] = CAMERA1_CONFIG["display_name"]
        data["CaptureMode"] = "MANUAL" if manual_mode else "AUTO"
        data["TimePeriod"] = get_current_time_based_config()
        
        # Add ROI clear status
        with roi_lock:
            data["ROIsClear"] = all_rois_clear
            data["ROIsCount"] = len(ROI_CONFIGS)
            roi_status_list = []
            for roi in ROI_CONFIGS:
                roi_status_list.append({
                    "name": roi["name"],
                    "is_clear": roi["is_clear"],
                    "reference_ready": roi["reference_ready"],
                    "similarity": float(np.mean(roi["match_history"])) if roi["match_history"] else 0.0
                })
            data["ROIStatus"] = roi_status_list
        
        if clear_time:
            data["ClearTargetTime"] = clear_time
            data["ClearTargetTimestamp"] = datetime.now().isoformat()
        
        if not is_capturing:
            if reason:
                data["CaptureStoppedReason"] = reason
            elif manual_mode:
                data["CaptureStoppedReason"] = "ManualStop"
            elif all_rois_clear and clear_time:
                data["CaptureStoppedReason"] = "TargetClearInBothROIs"
            else:
                data["CaptureStoppedReason"] = "TrainStartFalse"
            
            if clear_time:
                data["CaptureStoppedTime"] = clear_time
            else:
                data["CaptureStoppedTime"] = datetime.now().strftime("%H_%M_%S")
            
            capture_end_triggered = True
        elif is_capturing:
            data["CaptureStartedTime"] = datetime.now().strftime("%H_%M_%S")
            data["CaptureStoppedReason"] = "None"
            capture_end_triggered = False
        
        with open(CAPTURE_END_JSON_PATH, 'w') as file:
            json.dump(data, file, indent=4)
        
        return True
    except Exception as e:
        print(f"ERROR updating CaptureImageEnd.json: {e}")
        return False

def setup_output_folders(manual_mode=False):
    """Set up output folders for both cameras based on train ID from JSON"""
    global camera1_output_folder_path, camera2_output_folder_path, current_train_id
    global camera1_frame_counter, camera2_frame_counter, camera1_image_counter, camera2_image_counter
    global session_active, session_start_time, camera1_skip_pattern_index, camera2_skip_pattern_index
    global camera1_frame_id_counter, camera2_frame_id_counter, session_frame_counter
    
    train_id = get_train_id()
    if not train_id:
        print(f"WARNING: No valid train ID found in TrainId.json.")
        if manual_mode:
            print(f"  Manual capture requires a valid train ID from JSON.")
            return False
        else:
            print(f"  Auto capture cannot proceed without train ID.")
            return False
    
    current_train_id = train_id
    
    time_period = get_current_time_based_config()
    camera1_output_folder_path = get_output_folder_for_camera(CAMERA1_CONFIG, manual_mode, train_id)
    camera2_output_folder_path = get_output_folder_for_camera(CAMERA2_CONFIG, manual_mode, train_id)
    
    try:
        os.makedirs(camera1_output_folder_path, exist_ok=True)
        os.makedirs(camera2_output_folder_path, exist_ok=True)
        print(f"Created Camera 1 folder: {camera1_output_folder_path}")
        print(f"Created Camera 2 folder: {camera2_output_folder_path}")
        print(f"Time period: {time_period}")
    except Exception as e:
        print(f"ERROR: Failed to create output folders: {e}")
        return False
    
    if not session_active:
        session_active = True
        session_start_time = datetime.now()
        session_frame_counter = 0
        camera1_frame_id_counter = 0
        camera2_frame_id_counter = 0
        
        # Start Excel logging session
        excel_logger.start_session(train_id, camera1_output_folder_path)
        
        print(f"Session active: {session_start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    return True

def end_session():
    """End the current session for both cameras"""
    global save_frames, camera1_save_active, camera2_save_active, roi_tracking_active
    global session_active, session_start_time, current_train_id, capture_end_triggered
    global camera1_output_folder_path, camera2_output_folder_path
    global camera1_frame_counter, camera2_frame_counter
    global camera1_image_counter, camera2_image_counter
    global camera1_skip_pattern_index, camera2_skip_pattern_index
    global manual_capture_active, capture_mode
    global train_start_false_start_time, train_start_state
    global cooldown_active, cooldown_start_time
    global camera1_frame_id_counter, camera2_frame_id_counter
    global roi_reference_locked, all_rois_clear, target_clear_start_time
    
    if session_active:
        save_frames = False
        camera1_save_active = False
        camera2_save_active = False
        roi_tracking_active = False
        roi_reference_locked = False
        all_rois_clear = False
        target_clear_start_time = None
        capture_end_triggered = False
        manual_capture_active = False
        train_start_false_start_time = None
        train_start_state = False
        
        # Save Excel log before clearing
        excel_logger.save_log()
        
        # Clear queues when session ends
        clear_frame_queues()
        
        # Reset ROI tracking
        reset_roi_tracking()
        
        if capture_mode == "AUTO":
            cooldown_active = True
            cooldown_start_time = time.time()
            print(f"\n[COOLDOWN STARTED] Waiting {COOLDOWN_PERIOD} seconds")
        
        duration = datetime.now() - session_start_time if session_start_time else None
        time_period = get_current_time_based_config()
        
        print(f"\n[SESSION ENDED]")
        print(f"  Capture Mode: {capture_mode}")
        print(f"  Train ID: {current_train_id}")
        print(f"  Time Period: {time_period}")
        print(f"  Session Start: {session_start_time.strftime('%Y-%m-%d %H:%M:%S') if session_start_time else 'N/A'}")
        print(f"  Session End: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Camera 1 (BV) Images Saved: {camera1_image_counter}")
        print(f"  Camera 2 (SV) Images Saved: {camera2_image_counter}")
        print(f"  Total Images Saved: {camera1_image_counter + camera2_image_counter}")
        print(f"  Camera 1 Frame IDs: {camera1_frame_id_counter}")
        print(f"  Camera 2 Frame IDs: {camera2_frame_id_counter}")
        if duration:
            print(f"  Duration: {duration}")
        if capture_mode == "AUTO":
            print(f"  Cooldown: {COOLDOWN_PERIOD} seconds")
        print()
        
        session_active = False
        session_start_time = None
        current_train_id = ""
        
        camera1_output_folder_path = ""
        camera2_output_folder_path = ""
        camera1_frame_counter = 0
        camera2_frame_counter = 0
        camera1_image_counter = 0
        camera2_image_counter = 0
        camera1_skip_pattern_index = 0
        camera2_skip_pattern_index = 0
        camera1_frame_id_counter = 0
        camera2_frame_id_counter = 0
        
        return True
    
    return False

def clear_frame_queues():
    """Clear all frame queues to prevent stale data"""
    try:
        while not camera1_frame_queue.empty():
            try:
                camera1_frame_queue.get_nowait()
            except Empty:
                break
        
        while not camera2_frame_queue.empty():
            try:
                camera2_frame_queue.get_nowait()
            except Empty:
                break
    except Exception as e:
        print(f"Warning: Error clearing queues: {e}")

def start_capture(manual_mode=False):
    """Start capturing frames for both cameras with ROI tracking on Camera 1"""
    global save_frames, camera1_save_active, camera2_save_active, roi_tracking_active
    global capture_end_triggered, capture_mode, manual_capture_active
    global manual_capture_start_time, train_start_false_start_time
    global cooldown_active, cooldown_start_time
    global camera1_frame_counter, camera2_frame_counter
    global camera1_last_frame_time, camera2_last_frame_time
    global camera1_frame_id_counter, camera2_frame_id_counter
    global train_start_true_time, roi_reference_locked
    global all_rois_clear, target_clear_start_time
    
    if setup_output_folders(manual_mode):
        # Clear any old frames from queues
        clear_frame_queues()
        
        # Reset frame counters to ensure clean sequence
        with camera1_lock:
            camera1_frame_counter = 0
            camera1_frame_id_counter = 0
            camera1_last_frame_time = time.time()
        with camera2_lock:
            camera2_frame_counter = 0
            camera2_frame_id_counter = 0
            camera2_last_frame_time = time.time()
        
        save_frames = True
        camera1_save_active = True
        camera2_save_active = True
        capture_mode = "MANUAL" if manual_mode else "AUTO"
        manual_capture_active = manual_mode
        
        # Reset ROI tracking for new capture session
        reset_roi_tracking()
        
        if manual_mode:
            roi_tracking_active = False  # Disable ROI tracking in manual mode
            roi_reference_locked = False
            manual_capture_start_time = time.time()
            print(f"\n[MANUAL CAPTURE STARTED]")
        else:
            roi_tracking_active = True  # Enable ROI tracking in auto mode
            train_start_true_time = time.time()
            roi_reference_locked = False
            print(f"\n[AUTO CAPTURE STARTED - WITH ROI TRACKING]")
        
        train_start_false_start_time = None
        cooldown_active = False
        cooldown_start_time = None
        capture_end_triggered = False
        all_rois_clear = False
        target_clear_start_time = None
        
        time_period = get_current_time_based_config()
        
        print(f"  Camera 1 (BV): {CAMERA1_CONFIG['display_name']} (Serial: {CAMERA1_CONFIG['serial']})")
        print(f"  Resolution: {CAMERA1_CONFIG['resolution'][0]}x{CAMERA1_CONFIG['resolution'][1]}")
        print(f"  X Offset: {CAMERA1_CONFIG['x_offset']}, Y Offset: {CAMERA1_CONFIG['y_offset']}")
        print(f"  Camera 2 (SV): {CAMERA2_CONFIG['display_name']} (Serial: {CAMERA2_CONFIG['serial']})")
        print(f"  Resolution: {CAMERA2_CONFIG['resolution'][0]}x{CAMERA2_CONFIG['resolution'][1]}")
        print(f"  X Offset: {CAMERA2_CONFIG['x_offset']}, Y Offset: {CAMERA2_CONFIG['y_offset']}")
        print(f"  Train ID: {current_train_id}")
        print(f"  Time Period: {time_period}")
        print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Camera 1 Folder: {camera1_output_folder_path}")
        print(f"  Camera 2 Folder: {camera2_output_folder_path}")
        print(f"  Frame Skip Pattern: Save 1, Skip 2")
        print(f"  Filename Format: img[FRAME_ID]_[SEQ]_HH_MM_SS_milli_micro.jpg")
        print(f"  Queue Size: {FRAME_QUEUE_SIZE} frames (blocking mode)")
        print(f"  Target FPS: {TARGET_FPS} (stabilized)")
        print(f"  Buffer Mode: OldestFirst (preserves order)")
        print(f"  Excel Log: {LOG_FILENAME}")
        
        if manual_mode:
            print(f"  Capture Mode: MANUAL")
            print(f"  ROI Tracking: DISABLED in manual mode")
            print(f"  Stop Condition: Press 's' again to stop")
        else:
            print(f"  Capture Mode: AUTO")
            print(f"  ROI Tracking: ENABLED (Camera 1 only)")
            print(f"  ROI Lock Delay: {ROI_LOCK_DELAY} seconds")
            print(f"  Match Threshold: {MIN_ROI_MATCH_SCORE}")
            print(f"  Clear Target Duration: {CLEAR_TARGET_DURATION} seconds")
            print(f"  STOP CONDITION 1: BOTH ROIs on Camera 1 must be clear for {CLEAR_TARGET_DURATION}s")
            print(f"  STOP CONDITION 2: TrainStart=FALSE for {TRAIN_START_FALSE_DURATION}s")
            print(f"  Cooldown: {COOLDOWN_PERIOD}s after capture")
        
        print()
        update_capture_end_json(True, manual_mode=manual_mode)
        return True
    else:
        print(f"ERROR: Failed to start capture.")
        return False

def stop_capture(reason="ManualStop", clear_time=None):
    """Stop capturing frames for both cameras"""
    global save_frames, camera1_save_active, camera2_save_active, roi_tracking_active
    global roi_reference_locked, all_rois_clear, target_clear_start_time
    global capture_end_triggered, manual_capture_active, train_start_false_start_time
    
    if save_frames:
        save_frames = False
        camera1_save_active = False
        camera2_save_active = False
        roi_tracking_active = False
        roi_reference_locked = False
        all_rois_clear = False
        target_clear_start_time = None
        capture_end_triggered = False
        train_start_false_start_time = None
        
        duration = datetime.now() - session_start_time if session_start_time else None
        time_period = get_current_time_based_config()
        
        print(f"\n[CAPTURE STOPPED]")
        print(f"  Camera 1 (BV): {CAMERA1_CONFIG['display_name']}")
        print(f"  Camera 2 (SV): {CAMERA2_CONFIG['display_name']}")
        print(f"  Train ID: {current_train_id}")
        print(f"  Time Period: {time_period}")
        print(f"  Camera 1 Images: {camera1_image_counter}")
        print(f"  Camera 2 Images: {camera2_image_counter}")
        print(f"  Total Images: {camera1_image_counter + camera2_image_counter}")
        print(f"  Reason: {reason}")
        if duration:
            print(f"  Duration: {duration}")
        print()
        
        update_capture_end_json(False, clear_time, manual_mode=manual_capture_active, reason=reason)
        manual_capture_active = False
        end_session()
        return True
    
    return False

def toggle_manual_capture():
    """Toggle manual capture on/off"""
    global manual_capture_active, save_frames, cooldown_active
    
    with manual_lock:
        if not save_frames:
            if cooldown_active:
                current_time = time.time()
                cooldown_elapsed = current_time - cooldown_start_time if cooldown_start_time else 0
                cooldown_left = max(0, COOLDOWN_PERIOD - cooldown_elapsed)
                print(f"\n[WARNING] Cannot start manual capture during cooldown")
                print(f"  Cooldown active: {cooldown_left:.1f}s remaining")
                return False
            return start_capture(manual_mode=True)
        else:
            if manual_capture_active:
                clear_time = datetime.now().strftime("%H_%M_%S")
                return stop_capture(reason="ManualStop", clear_time=clear_time)
            else:
                print(f"\n[WARNING] Cannot stop manual capture while in auto mode")
                return False

def reset_roi_tracking():
    """Reset all ROI tracking variables"""
    global roi_frame_counter, all_rois_clear
    
    with roi_lock:
        roi_frame_counter = 0
        all_rois_clear = False
        
        for roi in ROI_CONFIGS:
            roi["reference_image"] = None
            roi["match_history"] = []
            roi["is_clear"] = False
            roi["clear_count"] = 0
            roi["reference_ready"] = False
            roi["frame_counter"] = 0
    
    print(f"[ROI TRACKING] Reset all ROI configurations")

def calculate_similarity(img1, img2):
    """Calculate similarity between two images using histogram correlation"""
    if img1 is None or img2 is None:
        return 0.0
    
    try:
        # Resize to same dimensions if needed
        if img1.shape != img2.shape:
            img2 = cv2.resize(img2, (img1.shape[1], img1.shape[0]))
        
        # Convert to grayscale if needed
        if len(img1.shape) == 3:
            img1_gray = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
            img2_gray = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
        else:
            img1_gray = img1
            img2_gray = img2
        
        # Calculate histograms
        hist1 = cv2.calcHist([img1_gray], [0], None, [256], [0, 256])
        hist2 = cv2.calcHist([img2_gray], [0], None, [256], [0, 256])
        
        # Normalize histograms
        hist1 = cv2.normalize(hist1, hist1).flatten()
        hist2 = cv2.normalize(hist2, hist2).flatten()
        
        # Calculate correlation
        similarity = cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL)
        
        # Convert to 0-1 range (correlation is -1 to 1)
        similarity = (similarity + 1) / 2
        
        return float(similarity)
        
    except Exception as e:
        print(f"ERROR calculating similarity: {e}")
        return 0.0

def extract_roi(frame, roi_config):
    """Extract ROI from frame based on relative coordinates"""
    if frame is None:
        return None, None
    
    try:
        height, width = frame.shape[:2]
        x1, y1, x2, y2 = roi_config["coords"]
        
        # Convert relative coordinates to absolute pixel coordinates
        abs_x1 = int(x1 * width)
        abs_y1 = int(y1 * height)
        abs_x2 = int(x2 * width)
        abs_y2 = int(y2 * height)
        
        # Ensure coordinates are within bounds
        abs_x1 = max(0, abs_x1)
        abs_y1 = max(0, abs_y1)
        abs_x2 = min(width, abs_x2)
        abs_y2 = min(height, abs_y2)
        
        # Extract ROI
        roi = frame[abs_y1:abs_y2, abs_x1:abs_x2]
        
        return roi, (abs_x1, abs_y1, abs_x2, abs_y2)
        
    except Exception as e:
        print(f"ERROR extracting ROI: {e}")
        return None, None

def update_roi_reference(frame):
    """Update ROI reference images from current frame (Camera 1 only)"""
    with roi_lock:
        for roi in ROI_CONFIGS:
            if not roi["reference_ready"]:
                roi_extracted, _ = extract_roi(frame, roi)
                if roi_extracted is not None:
                    roi["reference_image"] = roi_extracted.copy()
                    roi["frame_counter"] += 1
                    
                    if roi["frame_counter"] >= roi["reference_update_frames"]:
                        roi["reference_ready"] = True
                        print(f"[ROI REFERENCE] {roi['name']} reference image locked")

def check_all_rois_similarity(frame):
    """Check similarity between current frame ROIs and reference ROIs (Camera 1 only)"""
    global all_rois_clear, target_clear_start_time
    
    if frame is None:
        all_rois_clear = False
        target_clear_start_time = None
        return False
    
    current_time = time.time()
    
    with roi_lock:
        all_clear_now = True
        
        for roi in ROI_CONFIGS:
            if not roi["reference_ready"]:
                all_clear_now = False
                roi["is_clear"] = False
                roi["clear_count"] = 0
                continue
            
            # Extract current ROI
            roi_current, _ = extract_roi(frame, roi)
            if roi_current is None:
                all_clear_now = False
                roi["is_clear"] = False
                roi["clear_count"] = 0
                continue
            
            # Calculate similarity
            similarity = calculate_similarity(roi["reference_image"], roi_current)
            
            # Update match history
            roi["match_history"].append(similarity)
            if len(roi["match_history"]) > MAX_MATCH_HISTORY:
                roi["match_history"].pop(0)
            
            # Check if clear based on threshold
            is_clear = similarity >= MIN_ROI_MATCH_SCORE
            
            # Update clear count
            if is_clear:
                roi["clear_count"] += 1
                if roi["clear_count"] > roi["stability_frames"]:
                    roi["clear_count"] = roi["stability_frames"]
            else:
                roi["clear_count"] = max(0, roi["clear_count"] - 1)
            
            # Update clear state based on stability
            roi_clear_state = roi["clear_count"] >= roi["stability_frames"]
            roi["is_clear"] = roi_clear_state
            
            # If ANY ROI is not clear, then all are not clear
            if not roi_clear_state:
                all_clear_now = False
        
        # Update global all_rois_clear state
        all_rois_clear = all_clear_now
        
        # Handle target clear timing
        if all_rois_clear:
            if target_clear_start_time is None:
                target_clear_start_time = current_time
                print(f"[TARGET STATUS] BOTH ROIs now clear. Starting {CLEAR_TARGET_DURATION}s timer")
            else:
                # Check if clear for required duration
                duration_clear = current_time - target_clear_start_time
                if duration_clear >= CLEAR_TARGET_DURATION:
                    return True  # Target clear in BOTH ROIs for required duration
        else:
            # Reset timer if not all ROIs are clear
            if target_clear_start_time is not None:
                print(f"[TARGET STATUS] Lost clear in one or both ROIs. Resetting timer.")
            target_clear_start_time = None
    
    return False

def draw_roi_overlays(frame):
    """Draw ROI overlays on frame for display (Camera 1 only)"""
    if frame is None:
        return frame
    
    display_frame = frame.copy()
    height, width = display_frame.shape[:2]
    
    with roi_lock:
        for roi in ROI_CONFIGS:
            _, coords = extract_roi(frame, roi)
            if coords is None:
                continue
            
            x1, y1, x2, y2 = coords
            
            # Determine ROI color based on state
            if roi["reference_ready"]:
                if roi["is_clear"]:
                    color = (0, 255, 0)  # Green for clear
                else:
                    color = (0, 0, 255)  # Red for not clear
            else:
                color = (255, 255, 0)  # Yellow for setting up
            
            # Draw ROI rectangle
            cv2.rectangle(display_frame, (x1, y1), (x2, y2), color, 2)
            
            # Calculate average similarity from history
            avg_similarity = np.mean(roi["match_history"]) if roi["match_history"] else 0
            
            # ROI status text
            status = "CLEAR" if roi["is_clear"] else "NOT CLEAR"
            if not roi["reference_ready"]:
                status = f"SETUP {roi['frame_counter']}/{roi['reference_update_frames']}"
            
            # Draw ROI name and status
            text = f"{roi['name']}: {status} ({avg_similarity:.2f})"
            cv2.putText(display_frame, text, 
                       (x1, max(y1 - 10, 20)), cv2.FONT_HERSHEY_SIMPLEX, 
                       0.5, color, 1)
    
    # Draw target clear status
    if all_rois_clear and target_clear_start_time is not None:
        current_time = time.time()
        duration_clear = current_time - target_clear_start_time
        clear_time_left = max(0, CLEAR_TARGET_DURATION - duration_clear)
        
        clear_text = f"BOTH ROIs CLEAR: {clear_time_left:.1f}s left"
        cv2.putText(display_frame, clear_text, 
                   (width // 2 - 150, 30), cv2.FONT_HERSHEY_SIMPLEX, 
                   0.8, (0, 255, 0), 2)
    
    return display_frame

def save_frame_worker(camera_index):
    """Worker thread function to save frames from queue to disk"""
    global camera1_image_counter, camera2_image_counter
    global camera1_skip_pattern_index, camera2_skip_pattern_index
    
    camera_config = CAMERA_CONFIGS[camera_index]
    queue = camera1_frame_queue if camera_index == 0 else camera2_frame_queue
    
    print(f"  Saver thread for Camera {camera_index + 1} started")
    
    while not stop_saver_threads:
        try:
            # Get frame data from queue with timeout (blocking)
            frame_data = queue.get(timeout=0.5)
            
            if frame_data is None:
                continue
            
            # Extract frame data
            frame_obj = frame_data
            
            # Save the frame
            try:
                if camera_index == 0:
                    output_folder = camera1_output_folder_path
                    target_width = CAMERA1_CONFIG["resolution"][0]
                    target_height = CAMERA1_CONFIG["resolution"][1]
                    x_offset = CAMERA1_CONFIG["x_offset"]
                    y_offset = CAMERA1_CONFIG["y_offset"]
                    camera_name = CAMERA1_CONFIG["display_name"]
                else:
                    output_folder = camera2_output_folder_path
                    target_width = CAMERA2_CONFIG["resolution"][0]
                    target_height = CAMERA2_CONFIG["resolution"][1]
                    x_offset = CAMERA2_CONFIG["x_offset"]
                    y_offset = CAMERA2_CONFIG["y_offset"]
                    camera_name = CAMERA2_CONFIG["display_name"]
                
                frame = frame_obj.frame
                
                if frame.shape[1] != target_width or frame.shape[0] != target_height:
                    frame = cv2.resize(frame, (target_width, target_height))
                
                frame = apply_offset_to_frame(frame, x_offset, y_offset)
                
                # Generate filename using frame_id and sequence number
                filename = get_filename_from_sequence(
                    camera_index, 
                    frame_obj.frame_id,
                    frame_obj.sequence_number, 
                    frame_obj.timestamp_string
                )
                full_path = os.path.join(output_folder, filename)
                
                success = cv2.imwrite(full_path, frame, [cv2.IMWRITE_JPEG_QUALITY, IMAGE_QUALITY])
                
                if success:
                    if camera_index == 0:
                        with camera1_lock:
                            camera1_image_counter += 1
                            camera1_skip_pattern_index = frame_obj.pattern_index
                    else:
                        with camera2_lock:
                            camera2_image_counter += 1
                            camera2_skip_pattern_index = frame_obj.pattern_index
                    
                    # Log to Excel
                    timestamp_for_log = frame_obj.timestamp_string.replace('_', ':')
                    excel_logger.log_frame(
                        frame_obj.frame_id,
                        timestamp_for_log,
                        camera_name,
                        frame_obj.sequence_number,
                        filename
                    )
                    
                    # Print periodic status (less frequently)
                    if camera_index == 0 and camera1_image_counter % 10 == 0:
                        status_msg = f"  Camera 1 (BV): Saved image {camera1_image_counter:04d} (ID: {frame_obj.frame_id:06d}, Seq: {frame_obj.sequence_number:04d}) (FPS: {camera1_current_fps_display:.1f})"
                        if capture_mode == "AUTO" and roi_tracking_active:
                            with roi_lock:
                                if all_rois_clear and target_clear_start_time:
                                    duration_clear = time.time() - target_clear_start_time
                                    status_msg += f" | BOTH CLEAR: {duration_clear:.1f}s"
                                elif not all_rois_clear:
                                    status_msg += f" | NOT CLEAR"
                            if train_start_false_start_time is not None:
                                false_duration = time.time() - train_start_false_start_time
                                status_msg += f" | TrainStart FALSE: {false_duration:.1f}s"
                        elif capture_mode == "MANUAL":
                            status_msg += " | MANUAL MODE"
                        print(status_msg)
                    elif camera_index == 1 and camera2_image_counter % 10 == 0:
                        mode_text = "MANUAL" if capture_mode == "MANUAL" else "AUTO"
                        print(f"  Camera 2 (SV): Saved image {camera2_image_counter:04d} (ID: {frame_obj.frame_id:06d}, Seq: {frame_obj.sequence_number:04d}) (FPS: {camera2_current_fps_display:.1f}) | Mode: {mode_text}")
                else:
                    print(f"ERROR: Failed to save image to {full_path}")
            except Exception as e:
                print(f"ERROR: Error saving frame for camera {camera_index}: {e}")
            
            queue.task_done()
            
        except Empty:
            continue
        except Exception as e:
            print(f"ERROR in saver thread for camera {camera_index}: {e}")
            time.sleep(0.1)
    
    print(f"  Saver thread for Camera {camera_index + 1} stopped")

def update_fps_and_stabilize(camera_index):
    """Update FPS calculation and add delay to maintain target FPS"""
    global camera1_fps_counter, camera2_fps_counter
    global camera1_fps_timer, camera2_fps_timer
    global camera1_current_fps, camera2_current_fps
    global camera1_current_fps_display, camera2_current_fps_display
    global camera1_last_frame_time, camera2_last_frame_time
    global camera1_frame_times, camera2_frame_times
    
    current_time = time.time()
    
    if camera_index == 0:
        # Calculate time since last frame
        if camera1_last_frame_time > 0:
            frame_time = current_time - camera1_last_frame_time
            camera1_frame_times.append(frame_time)
            if len(camera1_frame_times) > MAX_FRAME_TIME_HISTORY:
                camera1_frame_times.pop(0)
        
        camera1_last_frame_time = current_time
        camera1_fps_counter += 1
        
        # Update FPS calculation every second
        time_diff = current_time - camera1_fps_timer
        if time_diff >= 1.0:
            camera1_current_fps = camera1_fps_counter / time_diff
            camera1_fps_counter = 0
            camera1_fps_timer = current_time
            camera1_current_fps_display = 0.9 * camera1_current_fps_display + 0.1 * camera1_current_fps
            
            # Log if FPS deviates significantly
            if abs(camera1_current_fps_display - TARGET_FPS) > FPS_TOLERANCE:
                avg_frame_time = sum(camera1_frame_times) / len(camera1_frame_times) if camera1_frame_times else 0
                print(f"  [FPS] Camera 1: {camera1_current_fps_display:.2f}/{TARGET_FPS}, Avg time {avg_frame_time*1000:.1f}ms")
        
        # Add delay if we're running too fast
        if len(camera1_frame_times) > 5:
            avg_frame_time = sum(camera1_frame_times[-5:]) / 5
            if avg_frame_time < FRAME_INTERVAL * 0.9:  # Running more than 10% too fast
                sleep_time = FRAME_INTERVAL - avg_frame_time
                if sleep_time > 0.001:  # Only sleep if more than 1ms
                    time.sleep(sleep_time * 0.5)  # Sleep half the needed time to avoid overshoot
    
    else:
        # Calculate time since last frame
        if camera2_last_frame_time > 0:
            frame_time = current_time - camera2_last_frame_time
            camera2_frame_times.append(frame_time)
            if len(camera2_frame_times) > MAX_FRAME_TIME_HISTORY:
                camera2_frame_times.pop(0)
        
        camera2_last_frame_time = current_time
        camera2_fps_counter += 1
        
        # Update FPS calculation every second
        time_diff = current_time - camera2_fps_timer
        if time_diff >= 1.0:
            camera2_current_fps = camera2_fps_counter / time_diff
            camera2_fps_counter = 0
            camera2_fps_timer = current_time
            camera2_current_fps_display = 0.9 * camera2_current_fps_display + 0.1 * camera2_current_fps
            
            # Log if FPS deviates significantly
            if abs(camera2_current_fps_display - TARGET_FPS) > FPS_TOLERANCE:
                avg_frame_time = sum(camera2_frame_times) / len(camera2_frame_times) if camera2_frame_times else 0
                print(f"  [FPS] Camera 2: {camera2_current_fps_display:.2f}/{TARGET_FPS}, Avg time {avg_frame_time*1000:.1f}ms")
        
        # Add delay if we're running too fast
        if len(camera2_frame_times) > 5:
            avg_frame_time = sum(camera2_frame_times[-5:]) / 5
            if avg_frame_time < FRAME_INTERVAL * 0.9:  # Running more than 10% too fast
                sleep_time = FRAME_INTERVAL - avg_frame_time
                if sleep_time > 0.001:  # Only sleep if more than 1ms
                    time.sleep(sleep_time * 0.5)  # Sleep half the needed time to avoid overshoot

def init_pyspin_system():
    """Initialize PySpin system"""
    global system, camera_list
    
    try:
        system = PySpin.System.GetInstance()
        version = system.GetLibraryVersion()
        print(f"PySpin library version: {version.major}.{version.minor}.{version.type}.{version.build}")
        
        camera_list = system.GetCameras()
        num_cameras = camera_list.GetSize()
        print(f"Number of cameras detected: {num_cameras}")
        
        if num_cameras < 2:
            print(f"ERROR: Only {num_cameras} camera(s) detected, but 2 are required!")
            return False
        
        print("\n[ALL DETECTED CAMERAS]")
        for i in range(num_cameras):
            cam = camera_list.GetByIndex(i)
            try:
                nodemap_tldevice = cam.GetTLDeviceNodeMap()
                serial_number = PySpin.CStringPtr(nodemap_tldevice.GetNode('DeviceSerialNumber')).GetValue()
                model_name = PySpin.CStringPtr(nodemap_tldevice.GetNode('DeviceModelName')).GetValue()
                print(f"  Camera {i}: {model_name} (Serial: {serial_number})")
            except:
                print(f"  Camera {i}: Unknown model/Serial")
            finally:
                del cam
        
        return True
    except PySpin.SpinnakerException as ex:
        print(f"ERROR: PySpin initialization failed: {ex}")
        return False

def find_camera_by_serial(target_serial):
    """Find a camera by its serial number"""
    global camera_list
    
    print(f"\n[SEARCHING FOR CAMERA WITH SERIAL: {target_serial}]")
    
    for i in range(camera_list.GetSize()):
        cam = camera_list.GetByIndex(i)
        try:
            nodemap_tldevice = cam.GetTLDeviceNodeMap()
            serial_number = PySpin.CStringPtr(nodemap_tldevice.GetNode('DeviceSerialNumber')).GetValue()
            model_name = PySpin.CStringPtr(nodemap_tldevice.GetNode('DeviceModelName')).GetValue()
            print(f"  Checking: {model_name} (Serial: {serial_number})")
            if serial_number == target_serial:
                print(f"  *** MATCH FOUND! ***")
                return cam
        except PySpin.SpinnakerException as ex:
            print(f"  Error reading camera {i}: {ex}")
            continue
        finally:
            if 'serial_number' in locals() and serial_number != target_serial:
                del cam
    
    print(f"  ERROR: Camera with serial {target_serial} not found!")
    return None

def configure_camera_network(cam):
    """Configure camera network settings"""
    try:
        print(f"\n[CONFIGURING NETWORK SETTINGS]")
        nodemap_tldevice = cam.GetTLDeviceNodeMap()
        device_type = PySpin.CStringPtr(nodemap_tldevice.GetNode('DeviceType')).GetValue()
        print(f"  Device Type: {device_type}")
        
        if 'GigE' in device_type or 'GEV' in device_type:
            print("  GigE Vision camera detected")
            try:
                nodemap = cam.GetNodeMap()
                ip_address_node = PySpin.CStringPtr(nodemap.GetNode('GevCurrentIPAddress'))
                subnet_mask_node = PySpin.CStringPtr(nodemap.GetNode('GevCurrentSubnetMask'))
                gateway_node = PySpin.CStringPtr(nodemap.GetNode('GevCurrentDefaultGateway'))
                
                if PySpin.IsAvailable(ip_address_node) and PySpin.IsReadable(ip_address_node):
                    current_ip = ip_address_node.GetValue()
                    current_subnet = subnet_mask_node.GetValue() if PySpin.IsAvailable(subnet_mask_node) else "N/A"
                    current_gateway = gateway_node.GetValue() if PySpin.IsAvailable(gateway_node) else "N/A"
                    print(f"  Current IP: {current_ip}")
                    print(f"  Current Subnet: {current_subnet}")
                    print(f"  Current Gateway: {current_gateway}")
            except Exception as e:
                print(f"  Could not read network configuration: {e}")
        else:
            print(f"  Camera uses {device_type} interface")
    except Exception as e:
        print(f"  ERROR configuring network: {e}")

def initialize_camera(cam, camera_config):
    """Initialize a camera with specific pixel format and resolution"""
    try:
        camera_name = camera_config['display_name']
        camera_serial = camera_config['serial']
        desired_pixel_format = camera_config['pixel_format']
        target_width = camera_config['resolution'][0]
        target_height = camera_config['resolution'][1]
        
        print(f"\n[INITIALIZING CAMERA]")
        print(f"  Camera: {camera_name}")
        print(f"  Serial: {camera_serial}")
        print(f"  Desired Pixel Format: {desired_pixel_format}")
        print(f"  Target Resolution: {target_width}x{target_height}")
        print(f"  X Offset: {camera_config['x_offset']}, Y Offset: {camera_config['y_offset']}")
        
        configure_camera_network(cam)
        cam.Init()
        
        nodemap = cam.GetTLDeviceNodeMap()
        device_model_name = PySpin.CStringPtr(nodemap.GetNode('DeviceModelName')).GetValue()
        device_serial_number = PySpin.CStringPtr(nodemap.GetNode('DeviceSerialNumber')).GetValue()
        print(f"  Model: {device_model_name}")
        print(f"  Serial: {device_serial_number}")
        
        print("\n[CONFIGURING CAMERA SETTINGS]")
        
        try:
            cam.AcquisitionMode.SetValue(PySpin.AcquisitionMode_Continuous)
            print("  Acquisition mode: Continuous")
        except Exception as e:
            print(f"  Warning: Could not set acquisition mode: {e}")
        
        try:
            pixel_format_entries = cam.PixelFormat.GetEntries()
            print(f"  Available pixel formats: {[entry.GetSymbolic() for entry in pixel_format_entries]}")
            
            if desired_pixel_format == "BayerRG8":
                if PySpin.IsAvailable(cam.PixelFormatBayerRG8):
                    cam.PixelFormat.SetValue(PySpin.PixelFormatBayerRG8)
                    print("  Pixel format set to: BayerRG8")
                elif PySpin.IsAvailable(cam.PixelFormat_RGB8):
                    cam.PixelFormat.SetValue(PySpin.PixelFormat_RGB8)
                    print("  Pixel format set to: RGB8")
                else:
                    print("  WARNING: BayerRG8 not available")
            elif desired_pixel_format == "Mono8":
                if PySpin.IsAvailable(cam.PixelFormat_Mono8):
                    cam.PixelFormat.SetValue(PySpin.PixelFormat_Mono8)
                    print("  Pixel format set to: Mono8")
                else:
                    print("  WARNING: Mono8 not available")
        except Exception as e:
            print(f"  Warning: Could not set pixel format: {e}")
        
        try:
            width_max = cam.Width.GetMax() if PySpin.IsAvailable(cam.Width) else 0
            height_max = cam.Height.GetMax() if PySpin.IsAvailable(cam.Height) else 0
            print(f"  Max resolution: {width_max}x{height_max}")
            
            actual_target_w = min(target_width, width_max) if width_max > 0 else target_width
            actual_target_h = min(target_height, height_max) if height_max > 0 else target_height
            
            if PySpin.IsAvailable(cam.Width) and PySpin.IsAvailable(cam.Height):
                cam.Width.SetValue(actual_target_w)
                cam.Height.SetValue(actual_target_h)
                print(f"  Resolution set to: {actual_target_w}x{actual_target_h}")
        except Exception as e:
            print(f"  Warning: Could not set resolution: {e}")
        
        apply_camera_settings_based_on_time(cam, camera_config)
        
        try:
            if PySpin.IsAvailable(cam.AcquisitionFrameRateEnable):
                cam.AcquisitionFrameRateEnable.SetValue(True)
            if PySpin.IsAvailable(cam.AcquisitionFrameRate):
                cam.AcquisitionFrameRate.SetValue(TARGET_FPS)
                print(f"  Frame rate set to: {TARGET_FPS} fps")
        except Exception as e:
            print(f"  Warning: Could not set frame rate: {e}")
        
        # Increase buffer count and set to OldestFirst to preserve frame order
        try:
            stream_nodemap = cam.GetTLStreamNodeMap()
            
            # Set buffer count mode to manual
            buffer_count_mode = PySpin.CEnumerationPtr(stream_nodemap.GetNode("StreamBufferCountMode"))
            if PySpin.IsAvailable(buffer_count_mode) and PySpin.IsWritable(buffer_count_mode):
                buffer_count_mode_manual = buffer_count_mode.GetEntryByName("Manual")
                if PySpin.IsAvailable(buffer_count_mode_manual):
                    buffer_count_mode.SetIntValue(buffer_count_mode_manual.GetValue())
                    print("  Buffer count mode: Manual")
            
            # Set buffer count
            buffer_count = PySpin.CIntegerPtr(stream_nodemap.GetNode("StreamBufferCountManual"))
            if PySpin.IsAvailable(buffer_count) and PySpin.IsWritable(buffer_count):
                buffer_count.SetValue(PYSPIN_BUFFER_COUNT)
                print(f"  Buffer count set to: {PYSPIN_BUFFER_COUNT}")
            
            # Set buffer handling mode to OldestFirst to preserve order
            buffer_mode = PySpin.CEnumerationPtr(stream_nodemap.GetNode("StreamBufferHandlingMode"))
            if PySpin.IsAvailable(buffer_mode) and PySpin.IsWritable(buffer_mode):
                buffer_mode_entry = buffer_mode.GetEntryByName("OldestFirst")
                if PySpin.IsAvailable(buffer_mode_entry):
                    buffer_mode.SetIntValue(buffer_mode_entry.GetValue())
                    print("  Buffer mode: OldestFirst (preserves order)")
        except Exception as e:
            print(f"  Warning: Could not set stream buffer settings: {e}")
        
        print("\n[CAMERA CONFIGURATION COMPLETE]")
        return True
    except PySpin.SpinnakerException as ex:
        print(f"ERROR: Failed to initialize camera {camera_config['display_name']}: {ex}")
        return False
    except Exception as ex:
        print(f"ERROR: Failed to initialize camera {camera_config['display_name']}: {ex}")
        return False

def camera_capture_thread(camera_index):
    """Thread function to capture frames from a camera"""
    global camera1_frame, camera2_frame, camera1_ready, camera2_ready
    global camera1_object, camera2_object, stop_threads
    global camera1_skip_pattern_index, camera2_skip_pattern_index
    global camera1_frame_counter, camera2_frame_counter
    global camera1_frame_id_counter, camera2_frame_id_counter
    
    camera_config = CAMERA_CONFIGS[camera_index]
    camera_name = camera_config['display_name']
    camera_serial = camera_config['serial']
    desired_pixel_format = camera_config['pixel_format']
    
    try:
        cam = find_camera_by_serial(camera_serial)
        if cam is None:
            print(f"ERROR: Camera {camera_index + 1} with serial {camera_serial} not found!")
            if camera_index == 0:
                camera1_ready = False
            else:
                camera2_ready = False
            return
        
        if camera_index == 0:
            camera1_object = cam
        else:
            camera2_object = cam
        
        if not initialize_camera(cam, camera_config):
            if camera_index == 0:
                camera1_ready = False
            else:
                camera2_ready = False
            return
        
        print(f"\n[STARTING ACQUISITION - Camera {camera_index + 1}]")
        cam.BeginAcquisition()
        
        if camera_index == 0:
            camera1_ready = True
        else:
            camera2_ready = True
        
        print(f"\n[CAMERA {camera_index + 1} READY]")
        print(f"  Camera: {camera_name}")
        print(f"  Serial: {camera_serial}")
        print(f"  Pixel Format: {desired_pixel_format}")
        print(f"  Resolution: {camera_config['resolution'][0]}x{camera_config['resolution'][1]}")
        print(f"  Target FPS: {TARGET_FPS}")
        print(f"  Acquisition started")
        
        bayer_format = None
        try:
            pixel_format = cam.PixelFormat.GetCurrentEntry().GetSymbolic()
            print(f"  Active pixel format: {pixel_format}")
            
            if "BayerRG8" in pixel_format:
                bayer_format = cv2.COLOR_BayerRG2BGR
                print("  Using BayerRG8 to BGR conversion")
            elif "BayerBG8" in pixel_format:
                bayer_format = cv2.COLOR_BayerBG2BGR
                print("  Using BayerBG8 to BGR conversion")
            elif "BayerGB8" in pixel_format:
                bayer_format = cv2.COLOR_BayerGB2BGR
                print("  Using BayerGB8 to BGR conversion")
            elif "BayerGR8" in pixel_format:
                bayer_format = cv2.COLOR_BayerGR2BGR
                print("  Using BayerGR8 to BGR conversion")
            elif "Mono8" in pixel_format:
                print("  Mono8 format, will convert to BGR for display")
                bayer_format = None
        except Exception as e:
            print(f"  Warning: Could not determine pixel format: {e}")
        
        print(f"\n[STARTING CAPTURE LOOP - Camera {camera_index + 1}]")
        error_count = 0
        max_errors = 10
        
        while not stop_threads and error_count < max_errors:
            try:
                # Use increased timeout
                image = cam.GetNextImage(GET_NEXT_IMAGE_TIMEOUT)
                
                if image.IsIncomplete():
                    status = image.GetImageStatus()
                    print(f"  Camera {camera_index + 1}: Image incomplete (status: {status})")
                    image.Release()
                    continue
                
                try:
                    image_data = image.GetNDArray()
                    
                    if image_data is not None and image_data.size > 0:
                        if bayer_format is not None:
                            frame = cv2.cvtColor(image_data, bayer_format)
                        elif desired_pixel_format == "Mono8":
                            frame = cv2.cvtColor(image_data, cv2.COLOR_GRAY2BGR)
                        else:
                            frame = image_data
                        
                        # Update FPS and apply stabilization delay
                        update_fps_and_stabilize(camera_index)
                        
                        # Create a single copy for display (only one copy needed)
                        display_frame = frame.copy()
                        
                        if camera_index == 0:
                            with camera1_lock:
                                camera1_frame = display_frame
                        else:
                            with camera2_lock:
                                camera2_frame = display_frame
                        
                        # Get current timestamp string at capture time
                        timestamp_string = get_timestamp_string()
                        
                        # Determine if frame should be saved based on skip pattern
                        if camera_index == 0:
                            should_save = camera1_save_active and SKIP_PATTERN[camera1_skip_pattern_index]
                            
                            # Get sequence number and frame ID BEFORE updating counters
                            with camera1_lock:
                                sequence_number = camera1_frame_counter
                                frame_id = camera1_frame_id_counter
                                camera1_frame_counter += 1
                                camera1_frame_id_counter += 1
                            
                            # Update pattern index for next frame
                            next_pattern_index = (camera1_skip_pattern_index + 1) % len(SKIP_PATTERN)
                            with camera1_lock:
                                camera1_skip_pattern_index = next_pattern_index
                        else:
                            should_save = camera2_save_active and SKIP_PATTERN[camera2_skip_pattern_index]
                            
                            # Get sequence number and frame ID BEFORE updating counters
                            with camera2_lock:
                                sequence_number = camera2_frame_counter
                                frame_id = camera2_frame_id_counter
                                camera2_frame_counter += 1
                                camera2_frame_id_counter += 1
                            
                            # Update pattern index for next frame
                            next_pattern_index = (camera2_skip_pattern_index + 1) % len(SKIP_PATTERN)
                            with camera2_lock:
                                camera2_skip_pattern_index = next_pattern_index
                        
                        # Push to queue for saving (if needed)
                        if save_frames and should_save:
                            # Create FrameData object with metadata - no extra copy needed
                            frame_obj = FrameData(
                                frame=frame,  # Use the original frame (no copy)
                                frame_id=frame_id,
                                sequence_number=sequence_number,
                                pattern_index=next_pattern_index,
                                timestamp_string=timestamp_string,
                                camera_name=camera_name
                            )
                            
                            # Use blocking put to ensure no frame drops
                            # This will wait if queue is full
                            try:
                                if camera_index == 0:
                                    camera1_frame_queue.put(frame_obj, block=True, timeout=None)
                                else:
                                    camera2_frame_queue.put(frame_obj, block=True, timeout=None)
                            except Exception as e:
                                print(f"  ERROR: Failed to queue frame for camera {camera_index}: {e}")
                        
                        error_count = 0
                    else:
                        print(f"  Camera {camera_index + 1}: Warning: Received empty frame")
                except Exception as e:
                    print(f"  Camera {camera_index + 1}: Error processing image: {e}")
                    error_count += 1
                
                image.Release()
            except PySpin.SpinnakerException as ex:
                if not stop_threads:
                    error_msg = str(ex)
                    print(f"  Camera {camera_index + 1}: Capture error: {error_msg}")
                    error_count += 1
                    time.sleep(0.5)
        
        if error_count >= max_errors:
            print(f"\n  Camera {camera_index + 1}: Too many errors ({error_count}), stopping capture")
        
        print(f"  Camera {camera_index + 1}: Capture loop stopped")
    except Exception as ex:
        print(f"\nERROR in camera {camera_index + 1} thread: {ex}")
        import traceback
        traceback.print_exc()
        if camera_index == 0:
            camera1_ready = False
        else:
            camera2_ready = False
    finally:
        print(f"\n[CLEANING UP CAMERA {camera_index + 1} THREAD]")
        cam_obj = camera1_object if camera_index == 0 else camera2_object
        if cam_obj is not None:
            try:
                if cam_obj.IsStreaming():
                    cam_obj.EndAcquisition()
                if cam_obj.IsInitialized():
                    cam_obj.DeInit()
                del cam_obj
                if camera_index == 0:
                    camera1_object = None
                else:
                    camera2_object = None
            except Exception as e:
                print(f"  Camera {camera_index + 1}: Error cleaning up camera: {e}")

def create_display_windows():
    """Create display windows for both cameras"""
    global display_windows_created
    try:
        window1_name = CAMERA1_CONFIG["display_window"]
        cv2.namedWindow(window1_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window1_name, 960, 540)
        
        window2_name = CAMERA2_CONFIG["display_window"]
        cv2.namedWindow(window2_name, cv2.WINDOW_NORMAL)
        display_width = 960
        display_height = int(960 * (1200/1950))
        cv2.resizeWindow(window2_name, display_width, display_height)
        
        print(f"  Created display window for Camera 1 (BV): {window1_name}")
        print(f"  Created display window for Camera 2 (SV): {window2_name}")
        display_windows_created = True
        return True
    except Exception as e:
        print(f"ERROR creating display windows: {e}")
        return False

def add_display_overlays(frame, camera_index):
    """Add all overlays to frame for display only (not saved)"""
    if frame is None:
        return None
    
    camera_config = CAMERA_CONFIGS[camera_index]
    
    # Start with ROI overlays for Camera 1 only (if in auto mode)
    if camera_index == 0 and capture_mode == "AUTO" and roi_tracking_active:
        display_frame = draw_roi_overlays(frame)
    else:
        display_frame = frame.copy()
    
    height, width = display_frame.shape[:2]
    camera_name = camera_config['display_name']
    camera_serial = camera_config['serial']
    camera_resolution = camera_config['resolution']
    time_period = get_current_time_based_config()
    
    # Camera name overlay
    cv2.putText(display_frame, f"Camera: {camera_name}", 
                (15, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
    cv2.putText(display_frame, f"Serial: {camera_serial}", 
                (15, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 255), 2)
    cv2.putText(display_frame, f"{camera_resolution[0]}x{camera_resolution[1]}", 
                (15, 95), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 255), 2)
    cv2.putText(display_frame, f"Offset X:{camera_config['x_offset']} Y:{camera_config['y_offset']}", 
                (15, 125), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (100, 255, 100), 1)
    
    period_color = (255, 255, 0) if time_period == "EVENING" else (0, 255, 255)
    cv2.putText(display_frame, f"Time: {time_period}", 
                (15, 155), cv2.FONT_HERSHEY_SIMPLEX, 0.7, period_color, 2)
    
    # FPS display with target
    if camera_index == 0:
        fps_text = f"FPS: {camera1_current_fps_display:.1f}/{TARGET_FPS}"
    else:
        fps_text = f"FPS: {camera2_current_fps_display:.1f}/{TARGET_FPS}"
    
    fps_text_size = cv2.getTextSize(fps_text, cv2.FONT_HERSHEY_SIMPLEX, 1.0, 3)[0]
    
    # Color based on stability
    if camera_index == 0:
        fps_diff = abs(camera1_current_fps_display - TARGET_FPS)
    else:
        fps_diff = abs(camera2_current_fps_display - TARGET_FPS)
    
    fps_color = (0, 255, 0) if fps_diff <= FPS_TOLERANCE else (0, 255, 255) if fps_diff <= 2.0 else (0, 0, 255)
    
    cv2.putText(display_frame, fps_text,
                (width - fps_text_size[0] - 20, 50), 
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, fps_color, 3)
    
    cv2.putText(display_frame, f"Format: {camera_config['pixel_format']}", 
                (15, 185), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 100, 255), 2)
    
    mode_color = (0, 255, 255) if capture_mode == "MANUAL" else (255, 255, 0)
    cv2.putText(display_frame, f"Mode: {capture_mode}", 
                (15, 215), cv2.FONT_HERSHEY_SIMPLEX, 0.7, mode_color, 2)
    
    if cooldown_active and cooldown_start_time:
        current_time = time.time()
        cooldown_elapsed = current_time - cooldown_start_time
        cooldown_left = max(0, COOLDOWN_PERIOD - cooldown_elapsed)
        cv2.putText(display_frame, f"COOLDOWN: {cooldown_left:.1f}s",
                   (15, 245), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
    else:
        # ROI Tracking Status (Camera 1 only)
        if camera_index == 0:
            if capture_mode == "AUTO":
                if roi_tracking_active:
                    roi_status = "ACTIVE"
                    if roi_reference_locked:
                        roi_status += " (REF LOCKED)"
                    else:
                        if train_start_true_time:
                            elapsed = time.time() - train_start_true_time
                            roi_status += f" (Setting up: {elapsed:.1f}/{ROI_LOCK_DELAY}s)"
                        else:
                            roi_status += " (Setting up)"
                    
                    cv2.putText(display_frame, f"ROI Tracking: {roi_status}", 
                                (15, 245), cv2.FONT_HERSHEY_SIMPLEX, 
                                0.7, (0, 255, 255), 2)
                    
                    # ROI Clear Status
                    if all_rois_clear:
                        roi_clear_text = "BOTH ROIs CLEAR"
                        roi_clear_color = (0, 255, 0)  # Green
                    else:
                        roi_clear_text = "ONE OR BOTH NOT CLEAR"
                        roi_clear_color = (0, 0, 255)  # Red
                        
                    cv2.putText(display_frame, roi_clear_text, 
                                (15, 275), cv2.FONT_HERSHEY_SIMPLEX, 
                                0.7, roi_clear_color, 2)
                    
                    # TrainStart False Timer (if active)
                    if train_start_false_start_time is not None:
                        current_time = time.time()
                        false_duration = current_time - train_start_false_start_time
                        false_time_left = max(0, TRAIN_START_FALSE_DURATION - false_duration)
                        
                        train_start_false_text = f"TrainStart FALSE: {false_time_left:.1f}s left"
                        cv2.putText(display_frame, train_start_false_text,
                                   (15, 305), cv2.FONT_HERSHEY_SIMPLEX,
                                   0.7, (0, 255, 255), 2)
                else:
                    cv2.putText(display_frame, "ROI Tracking: INACTIVE", 
                                (15, 245), cv2.FONT_HERSHEY_SIMPLEX, 
                                0.7, (255, 255, 255), 2)
            else:
                cv2.putText(display_frame, "MANUAL MODE", 
                            (15, 245), cv2.FONT_HERSHEY_SIMPLEX, 
                            0.7, (255, 255, 0), 2)
                cv2.putText(display_frame, "ROI Tracking: DISABLED", 
                            (15, 275), cv2.FONT_HERSHEY_SIMPLEX, 
                            0.7, (255, 255, 255), 2)
        else:
            cv2.putText(display_frame, f"FOLLOWING Camera 1", 
                        (15, 245), cv2.FONT_HERSHEY_SIMPLEX, 
                        0.7, (200, 100, 255), 2)
    
    # Queue status
    queue_size_1 = camera1_frame_queue.qsize()
    queue_size_2 = camera2_frame_queue.qsize()
    
    if camera_index == 0:
        queue_text = f"Queue: {queue_size_1}/{FRAME_QUEUE_SIZE}"
        queue_color = (0, 255, 0) if queue_size_1 < FRAME_QUEUE_SIZE * 0.8 else (0, 255, 255) if queue_size_1 < FRAME_QUEUE_SIZE else (0, 0, 255)
        cv2.putText(display_frame, queue_text, 
                    (15, 335 if camera_index == 0 and capture_mode == "AUTO" and roi_tracking_active else 305), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, queue_color, 1)
    else:
        queue_text = f"Queue: {queue_size_2}/{FRAME_QUEUE_SIZE}"
        queue_color = (0, 255, 0) if queue_size_2 < FRAME_QUEUE_SIZE * 0.8 else (0, 255, 255) if queue_size_2 < FRAME_QUEUE_SIZE else (0, 0, 255)
        cv2.putText(display_frame, queue_text, 
                    (15, 275), cv2.FONT_HERSHEY_SIMPLEX, 0.6, queue_color, 1)
    
    if save_frames:
        if camera_index == 0:
            status_text = f"CAPTURING: {camera1_image_counter}"
            pattern_text = f"Pattern: Save 1, Skip 2"
            frame_id_text = f"Frame ID: {camera1_frame_id_counter}"
        else:
            status_text = f"CAPTURING: {camera2_image_counter}"
            pattern_text = f"Pattern: Save 1, Skip 2"
            frame_id_text = f"Frame ID: {camera2_frame_id_counter}"
        
        status_color = (0, 255, 0) if capture_mode == "MANUAL" else (0, 0, 255)
        
        y_offset_base = 335 if camera_index == 0 and capture_mode == "AUTO" and roi_tracking_active else 305
        cv2.putText(display_frame, pattern_text, 
                    (15, y_offset_base), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 200, 0), 1)
        cv2.putText(display_frame, frame_id_text,
                    (15, y_offset_base + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 200, 0), 1)
        cv2.putText(display_frame, status_text, 
                    (15, y_offset_base + 60), cv2.FONT_HERSHEY_SIMPLEX, 0.8, status_color, 2)
        
        if camera_index == 0 and capture_mode == "AUTO" and roi_tracking_active:
            if all_rois_clear and target_clear_start_time is not None:
                current_time = time.time()
                duration_clear = current_time - target_clear_start_time
                clear_time_left = max(0, CLEAR_TARGET_DURATION - duration_clear)
                
                if clear_time_left > 0:
                    countdown_text = f"Stop in: {clear_time_left:.1f}s"
                    cv2.putText(display_frame, countdown_text,
                               (width // 2 - 100, height - 100),
                               cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
            elif train_start_false_start_time is not None:
                current_time = time.time()
                false_duration = current_time - train_start_false_start_time
                false_time_left = max(0, TRAIN_START_FALSE_DURATION - false_duration)
                
                if false_time_left > 0:
                    countdown_text = f"TrainStart FALSE: {false_time_left:.1f}s"
                    cv2.putText(display_frame, countdown_text,
                               (width // 2 - 150, height - 70),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 0), 2)
    else:
        cv2.putText(display_frame, "NOT CAPTURING", 
                    (15, 365), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    
    if current_train_id:
        display_id = current_train_id if len(current_train_id) <= 25 else current_train_id[:22] + "..."
        cv2.putText(display_frame, f"Train ID: {display_id}", 
                    (15, 395), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 100, 0), 2)
    
    current_time_str = datetime.now().strftime("%H:%M:%S")
    filename_format = "img[FRAME_ID]_[SEQ]_HH_MM_SS_milli_micro.jpg"
    time_text_size = cv2.getTextSize(current_time_str, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)[0]
    cv2.putText(display_frame, current_time_str, 
                (width - time_text_size[0] - 15, 35), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
    cv2.putText(display_frame, filename_format, 
                (width - 320, 65), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)
    
    if capture_mode == "AUTO" and not cooldown_active:
        train_start_status = check_train_start()
        train_status_text = f"TrainStart: {'TRUE' if train_start_status else 'FALSE'}"
        train_status_color = (0, 255, 0) if train_start_status else (0, 0, 255)
        cv2.putText(display_frame, train_status_text, 
                    (15, height - 40), cv2.FONT_HERSHEY_SIMPLEX, 0.6, train_status_color, 1)
    
    # CaptureEnd status
    if os.path.exists(CAPTURE_END_JSON_PATH):
        try:
            with open(CAPTURE_END_JSON_PATH, 'r') as f:
                capture_data = json.load(f)
                if "CaptureImageEnd" in capture_data:
                    capture_end_status = capture_data["CaptureImageEnd"]
                    status_text = f"CaptureEnd: {'TRUE' if capture_end_status else 'FALSE'}"
                    status_color = (0, 0, 255) if capture_end_status else (0, 255, 0)
                    cv2.putText(display_frame, status_text, 
                                (15, height - 70), cv2.FONT_HERSHEY_SIMPLEX, 
                                0.6, status_color, 1)
        except:
            pass
    
    controls_text = "q: Quit  |  s: Toggle Manual Save"
    cv2.putText(display_frame, controls_text, 
                (width // 2 - 150, height - 15), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
    
    return display_frame

def print_status_periodically():
    """Print status information periodically"""
    global last_status_check_time, last_save_notification
    global cooldown_active, cooldown_start_time
    global last_time_check, current_time_based_config
    
    current_time = time.time()
    
    if current_time - last_time_check >= time_check_interval:
        new_time_period = get_current_time_based_config()
        if new_time_period != current_time_based_config:
            current_time_based_config = new_time_period
            print(f"\n[TIME PERIOD CHANGED] Now: {current_time_based_config}")
            
            if not save_frames:
                if camera1_object is not None and camera1_object.IsInitialized():
                    apply_camera_settings_based_on_time(camera1_object, CAMERA1_CONFIG)
                if camera2_object is not None and camera2_object.IsInitialized():
                    apply_camera_settings_based_on_time(camera2_object, CAMERA2_CONFIG)
        last_time_check = current_time
    
    if current_time - last_status_check_time >= STATUS_CHECK_INTERVAL:
        last_status_check_time = current_time
        
        train_start_status = check_train_start()
        train_id = get_train_id()
        time_period = get_current_time_based_config()
        
        print(f"\n[SYSTEM STATUS - {datetime.now().strftime('%H:%M:%S')}]")
        print(f"  Time Period: {time_period}")
        print(f"  Camera 1 (BV): {CAMERA1_CONFIG['display_name']} (Serial: {CAMERA1_CONFIG['serial']})")
        print(f"    FPS: {camera1_current_fps_display:.2f}/{TARGET_FPS}")
        print(f"    Queue: {camera1_frame_queue.qsize()}/{FRAME_QUEUE_SIZE}")
        print(f"    Frame IDs: {camera1_frame_id_counter}")
        print(f"  Camera 2 (SV): {CAMERA2_CONFIG['display_name']} (Serial: {CAMERA2_CONFIG['serial']})")
        print(f"    FPS: {camera2_current_fps_display:.2f}/{TARGET_FPS}")
        print(f"    Queue: {camera2_frame_queue.qsize()}/{FRAME_QUEUE_SIZE}")
        print(f"    Frame IDs: {camera2_frame_id_counter}")
        print(f"  TrainStart: {'TRUE' if train_start_status else 'FALSE'}")
        print(f"  Train ID: {train_id if train_id else 'None'}")
        print(f"  Session Active: {session_active}")
        print(f"  Capture Mode: {capture_mode}")
        
        if cooldown_active and cooldown_start_time:
            cooldown_elapsed = current_time - cooldown_start_time
            cooldown_left = max(0, COOLDOWN_PERIOD - cooldown_elapsed)
            print(f"  COOLDOWN: {cooldown_left:.1f}s remaining")
        
        if capture_mode == "AUTO" and roi_tracking_active:
            with roi_lock:
                print(f"  ROI Tracking: {'ACTIVE' if roi_tracking_active else 'INACTIVE'}")
                print(f"  ROI Reference: {'LOCKED' if roi_reference_locked else 'SETTING UP'}")
                print(f"  ROI Clear Status: {'BOTH CLEAR' if all_rois_clear else 'ONE OR BOTH NOT CLEAR'}")
                for roi in ROI_CONFIGS:
                    avg_similarity = np.mean(roi["match_history"]) if roi["match_history"] else 0
                    status = "CLEAR" if roi["is_clear"] else "NOT CLEAR"
                    print(f"  {roi['name']}: {status} (Similarity: {avg_similarity:.2f})")
                
                if target_clear_start_time is not None and all_rois_clear:
                    duration_clear = current_time - target_clear_start_time
                    time_left = max(0, CLEAR_TARGET_DURATION - duration_clear)
                    print(f"  Clear Duration: {duration_clear:.1f}s / {CLEAR_TARGET_DURATION}s ({time_left:.1f}s left)")
        
        if save_frames:
            print(f"  Capturing: ACTIVE")
            print(f"  Train ID: {current_train_id}")
            print(f"  Camera 1 Images: {camera1_image_counter}")
            print(f"  Camera 2 Images: {camera2_image_counter}")
            print(f"  Total Images: {camera1_image_counter + camera2_image_counter}")
            
            if capture_mode == "AUTO" and train_start_false_start_time is not None:
                false_duration = current_time - train_start_false_start_time
                false_time_left = max(0, TRAIN_START_FALSE_DURATION - false_duration)
                print(f"  TrainStart FALSE: {false_duration:.1f}s / {TRAIN_START_FALSE_DURATION}s ({false_time_left:.1f}s left)")
        else:
            print(f"  Capturing: INACTIVE")
        print()
    
    if save_frames and current_time - last_save_notification >= save_notification_interval:
        last_save_notification = current_time
        status_msg = f"[CAPTURE PROGRESS] Camera 1: {camera1_image_counter}, Camera 2: {camera2_image_counter} images"
        status_msg += f" (FPS: {camera1_current_fps_display:.2f}/{camera2_current_fps_display:.2f})"
        status_msg += f" | Queues: {camera1_frame_queue.qsize()}/{camera2_frame_queue.qsize()}"
        status_msg += f" | Frame IDs: {camera1_frame_id_counter}/{camera2_frame_id_counter}"
        
        if capture_mode == "AUTO" and roi_tracking_active:
            if all_rois_clear and target_clear_start_time:
                duration_clear = current_time - target_clear_start_time
                status_msg += f" | BOTH ROIs clear for {duration_clear:.1f}s"
            elif train_start_false_start_time is not None:
                false_duration = current_time - train_start_false_start_time
                status_msg += f" | TrainStart FALSE for {false_duration:.1f}s"
        
        if capture_mode == "MANUAL":
            status_msg += " | MANUAL MODE"
        print(status_msg)

def cleanup_all():
    """Clean up all PySpin resources"""
    global system, camera_list, stop_threads, stop_saver_threads
    
    print("\n[SHUTTING DOWN] Cleaning up resources...")
    stop_threads = True
    stop_saver_threads = True
    time.sleep(1.0)
    
    # Save any remaining logs
    excel_logger.save_log()
    
    if camera_list is not None:
        print("  Clearing camera list...")
        camera_list.Clear()
    
    if system is not None:
        print("  Releasing PySpin system...")
        system.ReleaseInstance()
    
    print("  Closing display windows...")
    cv2.destroyAllWindows()
    print("  Cleanup completed")

def main():
    global save_frames, camera1_save_active, camera2_save_active, roi_tracking_active
    global camera1_frame, camera2_frame, camera1_ready, camera2_ready, stop_threads
    global camera1_skip_pattern_index, camera2_skip_pattern_index
    global capture_end_triggered, current_train_id, train_start_state
    global manual_capture_active, capture_mode, train_start_false_start_time
    global cooldown_active, cooldown_start_time, last_time_check, current_time_based_config
    global stop_saver_threads, roi_reference_locked, train_start_true_time
    global all_rois_clear, target_clear_start_time
    
    print("\n" + "="*60)
    print("DUAL CAMERA MACHINE VISION RECORDER WITH ROI TRACKING")
    print("="*60)
    print(f"Camera 1 (BV - ROI Tracking): {CAMERA1_CONFIG['display_name']} (Serial: {CAMERA1_CONFIG['serial']})")
    print(f"  Resolution: {CAMERA1_CONFIG['resolution'][0]}x{CAMERA1_CONFIG['resolution'][1]}")
    print(f"  Output (Morning): {CAMERA1_CONFIG['output_folder']}")
    print(f"  Output (Evening): {CAMERA1_CONFIG['output_folder_raw']}")
    print(f"\nCamera 2 (SV - Synchronized): {CAMERA2_CONFIG['display_name']} (Serial: {CAMERA2_CONFIG['serial']})")
    print(f"  Resolution: {CAMERA2_CONFIG['resolution'][0]}x{CAMERA2_CONFIG['resolution'][1]}")
    print(f"  Output (Morning): {CAMERA2_CONFIG['output_folder']}")
    print(f"  Output (Evening): {CAMERA2_CONFIG['output_folder_raw']}")
    print(f"\nROI Configurations:")
    for i, roi in enumerate(ROI_CONFIGS):
        print(f"  ROI {i+1}: {roi['name']} - Coords: {roi['coords']}")
    print(f"\nCommon Settings:")
    print(f"  Frame Skip Pattern: Save 1, Skip 2")
    print(f"  Filename Format: img[FRAME_ID]_[SEQ]_HH_MM_SS_milli_micro.jpg")
    print(f"  AUTO Stop Condition 1: BOTH ROIs clear for {CLEAR_TARGET_DURATION}s")
    print(f"  AUTO Stop Condition 2: TrainStart=FALSE for {TRAIN_START_FALSE_DURATION}s")
    print(f"  Cooldown: {COOLDOWN_PERIOD}s after capture")
    print(f"  Time Periods: MORNING (6AM-5PM), EVENING (5PM-6AM)")
    print(f"\n[PERFORMANCE OPTIMIZATIONS]")
    print(f"  Producer-Consumer Architecture")
    print(f"  Frame Queue Size: {FRAME_QUEUE_SIZE} frames per camera (blocking mode)")
    print(f"  Saver Threads: 1 per camera (FIFO order)")
    print(f"  PySpin Buffers: {PYSPIN_BUFFER_COUNT} (OldestFirst mode)")
    print(f"  GetNextImage Timeout: {GET_NEXT_IMAGE_TIMEOUT}ms")
    print(f"  Frame IDs: Assigned at capture time (unique sequential)")
    print(f"  Excel Log: {LOG_FILENAME} (frame tracking)")
    print(f"\n[FPS STABILIZATION]")
    print(f"  Target FPS: {TARGET_FPS}")
    print(f"  Frame Interval: {FRAME_INTERVAL*1000:.1f}ms")
    print(f"  Tolerance: ±{FPS_TOLERANCE} FPS")
    print("="*60)
    
    last_time_check = time.time()
    current_time_based_config = get_current_time_based_config()
    
    print("\n[INITIALIZING Pyspin]")
    if not init_pyspin_system():
        print("ERROR: Failed to initialize PySpin system")
        return
    
    print("\n[STARTING CAMERA THREADS]")
    camera_threads = []
    
    for i in range(2):
        print(f"\nStarting thread for Camera {i+1}: {CAMERA_CONFIGS[i]['display_name']}")
        thread = threading.Thread(target=camera_capture_thread, args=(i,))
        thread.daemon = True
        thread.start()
        camera_threads.append(thread)
        time.sleep(1)
    
    print("\n[STARTING SAVER THREADS]")
    saver_threads = []
    stop_saver_threads = False
    
    # Start ONE saver thread per camera
    for i in range(2):
        thread = threading.Thread(target=save_frame_worker, args=(i,))
        thread.daemon = True
        thread.start()
        saver_threads.append(thread)
    
    print("\n[WAITING FOR CAMERAS]")
    max_wait_time = 30
    start_wait = time.time()
    
    while time.time() - start_wait < max_wait_time and (not camera1_ready or not camera2_ready):
        time.sleep(0.5)
        ready_count = (1 if camera1_ready else 0) + (1 if camera2_ready else 0)
        print(f". ({ready_count}/2 cameras ready)", end="", flush=True)
    
    print()
    
    print(f"\n[CAMERA CONNECTION STATUS]")
    if camera1_ready:
        print(f"  Camera 1 (BV): CONNECTED")
    else:
        print(f"  Camera 1 (BV): FAILED")
    
    if camera2_ready:
        print(f"  Camera 2 (SV): CONNECTED")
    else:
        print(f"  Camera 2 (SV): FAILED")
    
    if not camera1_ready or not camera2_ready:
        print(f"\nERROR: Not all cameras connected!")
        cleanup_all()
        return
    
    print("\n[CREATING DISPLAY WINDOWS]")
    create_display_windows()
    
    print("\n" + "="*60)
    print("[READY - CONTROLS]")
    print("  q: Quit program")
    print("  s: Start/Stop MANUAL capture")
    print("="*60)
    print("[CAPTURE MODES]")
    print("  AUTO: Controlled by TrainStart.json with ROI tracking")
    print(f"    ROI Lock Delay: {ROI_LOCK_DELAY}s after train start")
    print(f"    Match Threshold: {MIN_ROI_MATCH_SCORE}")
    print(f"    Stop Condition 1: BOTH ROIs clear for {CLEAR_TARGET_DURATION}s")
    print(f"    Stop Condition 2: TrainStart=FALSE for {TRAIN_START_FALSE_DURATION}s")
    print(f"    Cooldown: {COOLDOWN_PERIOD}s after capture")
    print("  MANUAL: Controlled by 's' key")
    print("="*60)
    print("[FILENAME FORMAT]")
    print("  img[FRAME_ID]_[SEQ]_HH_MM_SS_milli_micro.jpg")
    print("  Frame ID ensures unique identification across captures")
    print("  Sequence number tracks capture order within session")
    print("="*60)
    print("[EXCEL LOGGING]")
    print(f"  Log file: {LOG_FILENAME}")
    print("  Logs: Frame ID, Timestamp, Camera, Sequence, Filename")
    print("="*60)
    print("[FPS TARGET]")
    print(f"  {TARGET_FPS} FPS (stabilized)")
    print("="*60)
    
    last_status_check = time.time()
    last_json_check = time.time()
    last_frame_time = time.time()
    frame_display_count = 0
    
    camera1_skip_pattern_index = 0
    camera2_skip_pattern_index = 0
    
    # Initialize ROI tracking
    reset_roi_tracking()
    
    try:
        while True:
            current_time = time.time()
            
            if current_time - last_time_check >= time_check_interval:
                new_time_period = get_current_time_based_config()
                if new_time_period != current_time_based_config:
                    current_time_based_config = new_time_period
                    print(f"\n[TIME PERIOD CHANGED] Now: {current_time_based_config}")
                    
                    if not save_frames:
                        if camera1_object is not None and camera1_object.IsInitialized():
                            apply_camera_settings_based_on_time(camera1_object, CAMERA1_CONFIG)
                        if camera2_object is not None and camera2_object.IsInitialized():
                            apply_camera_settings_based_on_time(camera2_object, CAMERA2_CONFIG)
                last_time_check = current_time
            
            if cooldown_active and cooldown_start_time:
                cooldown_elapsed = current_time - cooldown_start_time
                if cooldown_elapsed >= COOLDOWN_PERIOD:
                    print(f"\n[COOLDOWN COMPLETED]")
                    cooldown_active = False
                    cooldown_start_time = None
                else:
                    last_json_check = current_time
            
            if not cooldown_active and capture_mode != "MANUAL" and current_time - last_json_check >= 0.5:
                current_train_start = check_train_start()
                last_json_check = current_time
                
                if capture_mode == "AUTO" and roi_tracking_active and save_frames:
                    if not current_train_start:
                        if train_start_false_start_time is None:
                            train_start_false_start_time = current_time
                            print(f"[TRAIN START] TrainStart=FALSE, starting {TRAIN_START_FALSE_DURATION}s timer")
                        else:
                            false_duration = current_time - train_start_false_start_time
                            if false_duration >= TRAIN_START_FALSE_DURATION:
                                print(f"[TRAIN START] TrainStart FALSE for {TRAIN_START_FALSE_DURATION}s, stopping capture")
                                stop_capture(reason=f"TrainStartFalseFor{TRAIN_START_FALSE_DURATION}s")
                                continue
                    else:
                        if train_start_false_start_time is not None:
                            print(f"[TRAIN START] TrainStart changed back to TRUE, resetting timer")
                            train_start_false_start_time = None
                
                if not cooldown_active and not train_start_state and current_train_start:
                    print(f"\n[TRIGGER DETECTED] TrainStart TRUE - Starting AUTO capture with ROI tracking")
                    start_capture(manual_mode=False)
                
                train_start_state = current_train_start
            
            if current_time - last_status_check >= STATUS_CHECK_INTERVAL:
                print_status_periodically()
                last_status_check = current_time
            
            with camera1_lock:
                frame1 = camera1_frame.copy() if camera1_frame is not None else None
            with camera2_lock:
                frame2 = camera2_frame.copy() if camera2_frame is not None else None
            
            if frame1 is not None:
                frame_display_count += 1
                
                # Keep a clean copy for ROI tracking
                clean_frame1 = frame1.copy()
                
                # ROI Tracking (Camera 1 only)
                if capture_mode == "AUTO" and roi_tracking_active and save_frames:
                    # Check if we should lock ROI reference (after delay)
                    if not roi_reference_locked:
                        if train_start_true_time and (current_time - train_start_true_time >= ROI_LOCK_DELAY):
                            print(f"[ROI LOCKED] Setting reference images after {ROI_LOCK_DELAY} seconds")
                            update_roi_reference(clean_frame1)
                            roi_reference_locked = True
                        else:
                            # Update ROI reference during setup phase
                            update_roi_reference(clean_frame1)
                    
                    # Check ALL ROIs similarity if reference is locked
                    if roi_reference_locked:
                        # Check if BOTH ROIs are clear for required duration
                        target_clear_in_both = check_all_rois_similarity(clean_frame1)
                        
                        # If target is clear in BOTH ROIs for required duration, stop capture for both cameras
                        if target_clear_in_both and not capture_end_triggered:
                            clear_time = datetime.now().strftime("%H_%M_%S")
                            print(f"\n[TARGET CLEAR IN BOTH ROIs] Target visible in BOTH ROIs for {CLEAR_TARGET_DURATION} seconds")
                            print(f"  Stopping both cameras at {clear_time}")
                            
                            # Stop capture for both cameras
                            stop_capture(reason="TargetClearInBothROIs", clear_time=clear_time)
                
                display_frame1 = add_display_overlays(frame1, 0)
                if display_frame1 is not None:
                    cv2.imshow(CAMERA1_CONFIG["display_window"], display_frame1)
                    last_frame_time = current_time
            
            if frame2 is not None:
                display_frame2 = add_display_overlays(frame2, 1)
                if display_frame2 is not None:
                    cv2.imshow(CAMERA2_CONFIG["display_window"], display_frame2)
            
            if frame1 is None and frame2 is None and current_time - last_frame_time > 2:
                black_frame = np.zeros((540, 960, 3), dtype=np.uint8)
                status_text = "WAITING FOR FRAMES" if camera1_ready and camera2_ready else "CAMERAS NOT CONNECTED"
                color = (0, 0, 255) if camera1_ready and camera2_ready else (255, 0, 0)
                cv2.putText(black_frame, status_text, 
                           (960//2 - 200, 540//2 - 40), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 2)
                cv2.putText(black_frame, f"Dual Camera System with ROI Tracking", 
                           (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 1)
                cv2.putText(black_frame, f"Mode: {capture_mode} | Press 's' for manual", 
                           (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 1)
                cv2.imshow(CAMERA1_CONFIG["display_window"], black_frame)
                cv2.imshow(CAMERA2_CONFIG["display_window"], black_frame)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                if save_frames:
                    reason = "ManualQuit" if manual_capture_active else "AutoQuit"
                    stop_capture(reason=reason)
                break
            elif key == ord('s'):
                if not save_frames or manual_capture_active:
                    toggle_manual_capture()
                else:
                    print(f"\n[WARNING] Cannot start manual capture while in auto mode")
    
    except KeyboardInterrupt:
        print("\n\n[INTERRUPTED] User interrupted")
    except Exception as e:
        print(f"\n\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
    finally:
        stop_saver_threads = True
        cleanup_all()
        
        print(f"\n[PROGRAM ENDED]")
        print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Camera 1 Images Saved: {camera1_image_counter}")
        print(f"  Camera 2 Images Saved: {camera2_image_counter}")
        print(f"  Total Images Saved: {camera1_image_counter + camera2_image_counter}")
        print(f"  Camera 1 Frame IDs: {camera1_frame_id_counter}")
        print(f"  Camera 2 Frame IDs: {camera2_frame_id_counter}")
        print(f"  Final Mode: {capture_mode}")
        print()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n\n[FATAL ERROR] {e}")
        import traceback
        traceback.print_exc()
        cleanup_all()
    finally:
        print("Program terminated")
