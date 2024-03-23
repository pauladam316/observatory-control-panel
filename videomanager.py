from nicegui import Client, app, core, run, ui
import time
from fastapi import Response
import base64
import cv2
import numpy as np
import serial
from fastapi_utils.tasks import repeat_every
import struct
from dataclasses import dataclass
import yaml
from threading import Thread, Lock

class VideoManager:
    # In case you don't have a webcam, this will provide a black placeholder image.
    black_1px = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAAXNSR0IArs4c6QAAAA1JREFUGFdjYGBg+A8AAQQBAHAgZQsAAAAASUVORK5CYII='
    placeholder = Response(content=base64.b64decode(black_1px.encode('ascii')), media_type='image/png')
    # OpenCV is used to access the webcam.
    
    def convert(frame: np.ndarray) -> bytes:
        _, imencode_image = cv2.imencode('.jpg', frame)
        return imencode_image.tobytes()

    def __init__(self, credential_file: str):
        with open(credential_file, 'r') as file:
            credentials = yaml.safe_load(file)
        # Access the username and password
        username = credentials['username']
        password = credentials['password']
        ip = credentials['ip']
        self.video_capture = cv2.VideoCapture(f"rtsp://{username}:{password}@{ip}/stream2")
        # Initialize variables to hold the latest frame and a lock for thread-safe operations
        self.latest_frame = None
        self.lock = Lock()

        # Start the background frame reading task
        self.read_frames_continuously()

    def read_frames_continuously(self):
        """Read frames in a separate thread and update the latest frame."""
        def read_loop():
            while True:
                if self.video_capture.isOpened():
                    success, frame = self.video_capture.read()
                    if success:
                        with self.lock:
                            self.latest_frame = frame
        # Start the thread
        #Thread(target=read_loop, daemon=True).start()

    async def grab_video_frame(self) -> Response:
        with self.lock:
            # Check if we have a frame available
            if self.latest_frame is None:
                return VideoManager.placeholder
            frame = self.latest_frame

        # Convert the frame (this operation is CPU-intensive and might be async executed)
        jpeg = await run.cpu_bound(VideoManager.convert, frame)
        return Response(content=jpeg, media_type='image/jpeg')

# Dictionary to hold VideoManager instances
video_managers = {
    "observatory_cam": VideoManager("observatory_cam.yaml"),
    #"cloud_cam": VideoManager("rtsp://your_second_camera_url"),
    # Add more cameras as needed
}

@app.get('/video/frame/{camera_id}')
# Thanks to FastAPI's `app.get`` it is easy to create a web route which always provides the latest image from OpenCV.
async def grab_video_frame(camera_id: str) -> Response:
    video_manager = video_managers.get(camera_id)
    if not video_manager:
        return Response(content="Camera ID not found", status_code=404)
    return await video_manager.grab_video_frame()
