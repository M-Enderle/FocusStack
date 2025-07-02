"""
Sony Imaging Edge Remote Camera Control Module

This module provides a comprehensive interface for controlling Sony cameras through
the Imaging Edge Remote application using Windows API automation. It handles window
management, keyboard input simulation, screenshot capture, and image processing for
automated focus stacking operations.
"""

import time
import win32con
import win32api
import win32gui
from PIL import ImageGrab
import cv2
import numpy as np
from pywinauto.application import Application


class ImagingEdgeRemote:
    """
    Controller for Sony Imaging Edge Remote application automation.
    
    Provides high-level methods for camera control including focus adjustment,
    image capture, and status monitoring through screenshot analysis and
    keyboard automation.
    """
    
    def __init__(self, exe_path: str = r"C:\Program Files\Sony\Imaging Edge\Remote.exe", 
                 window_title_re: str = r".*Remote.*"):
        """
        Initialize connection to Imaging Edge Remote application.

        Args:
            exe_path (str): Path to the Imaging Edge Remote executable
            window_title_re (str): Regex pattern to match the window title
        
        Raises:
            pywinauto.application.AppNotConnected: If application cannot be connected
        """
        self.exe_path = exe_path
        self.window_title_re = window_title_re
        self.app = Application(backend="uia").connect(path=self.exe_path)
        self.window = self.app.window(title_re=self.window_title_re)

    def focus(self):
        """Bring the Imaging Edge Remote window to the foreground."""
        self.window.set_focus()

    def capture_image(self):
        """Trigger camera to capture an image by sending the '1' key."""
        self._send_key('1')

    def capture_screenshot(self):
        """
        Capture screenshot of the Imaging Edge Remote window.

        Returns:
            PIL.Image: Screenshot of the application window
        """
        hwnd = self.window.handle
        rect = win32gui.GetWindowRect(hwnd)
        return ImageGrab.grab(bbox=rect)

    def focus_far(self, steps: int, time_per_step: float = 0.08):
        """
        Adjust focus toward farther distances.
        
        Args:
            steps (int): Number of focus steps to move
            time_per_step (float): Delay between individual key presses
        """
        self._execute_focus_movement(steps, time_per_step, far_direction=True)

    def focus_near(self, steps: int, time_per_step: float = 0.08):
        """
        Adjust focus toward nearer distances.
        
        Args:
            steps (int): Number of focus steps to move  
            time_per_step (float): Delay between individual key presses
        """
        self._execute_focus_movement(steps, time_per_step, far_direction=False)

    def wait_for_camera_to_be_ready(self):
        """
        Block until camera is ready for next operation.
        
        Monitors the brightness indicator template until sufficient brightness
        is detected, indicating camera readiness.
        """
        while True:
            screenshot = self.capture_screenshot()
            brightness = self._find_brightest_pixel(screenshot, 'brightness.png', 0.9)
            if brightness and brightness > 200:
                return
            time.sleep(0.1)

    def wait_for_transfer(self, template_path: str = "files.png", threshold: float = 0.985):
        """
        Block until file transfer operation completes.

        Args:
            template_path (str): Path to template image indicating completion
            threshold (float): Confidence threshold for template matching (0.0-1.0)
        """
        while True:
            screenshot = self.capture_screenshot()
            if self._is_transfer_complete(screenshot, template_path, threshold):
                return
            time.sleep(0.1)

    def _execute_focus_movement(self, steps: int, time_per_step: float, far_direction: bool):
        """
        Execute focus movement in specified direction with optimized key sequences.
        
        Args:
            steps (int): Total number of focus steps to move
            time_per_step (float): Delay between key presses
            far_direction (bool): True for far direction, False for near
        """
        # Key mappings for focus directions
        if far_direction:
            single_key, large_key, opposite_key = 't', 'y', 'w'
        else:
            single_key, large_key, opposite_key = 'w', 'q', 't'
        
        remaining_steps = steps
        while remaining_steps > 0:
            if remaining_steps < 26:
                # Use individual steps for small movements
                for _ in range(remaining_steps):
                    self._send_key(single_key)
                    time.sleep(time_per_step)
                break
            elif remaining_steps <= 50:
                # Use large step then back-adjust
                self._send_key(large_key)
                back_steps = 50 - remaining_steps
                for _ in range(back_steps):
                    self._send_key(opposite_key)
                    time.sleep(time_per_step)
                break
            else:
                # Use large steps for efficient movement
                self._send_key(large_key)
                time.sleep(time_per_step)
                remaining_steps -= 50

    def _send_key(self, key: str, shift: bool = False):
        """
        Send keyboard input to the application window.

        Args:
            key (str): Single character key to send
            shift (bool): Whether to hold Shift during key press
        """
        hwnd = self.window.handle
        key_code = ord(key.upper())
        
        if shift:
            win32api.PostMessage(hwnd, win32con.WM_KEYDOWN, win32con.VK_SHIFT, 0)
        
        win32api.PostMessage(hwnd, win32con.WM_KEYDOWN, key_code, 0)
        win32api.PostMessage(hwnd, win32con.WM_KEYUP, key_code, 0)
        
        if shift:
            win32api.PostMessage(hwnd, win32con.WM_KEYUP, win32con.VK_SHIFT, 0)

    def _find_brightest_pixel(self, screenshot_img, template_path: str, threshold: float = 0.95):
        """
        Locate brightest pixel within a template-matched region.

        Args:
            screenshot_img: PIL Image of the screenshot
            template_path (str): Path to template image file
            threshold (float): Minimum confidence for template matching

        Returns:
            int or None: Maximum brightness value (0-255) or None if no match
            
        Raises:
            FileNotFoundError: If template image cannot be loaded
        """
        screenshot_cv = cv2.cvtColor(np.array(screenshot_img), cv2.COLOR_RGB2BGR)
        template = cv2.imread(template_path, cv2.IMREAD_COLOR)
        
        if template is None:
            raise FileNotFoundError(f"Template image not found: {template_path}")
        
        # Perform template matching
        result = cv2.matchTemplate(screenshot_cv, template, cv2.TM_CCOEFF_NORMED)
        _, max_confidence, _, max_location = cv2.minMaxLoc(result)
        
        if max_confidence < threshold:
            return None
        
        # Extract matched region and find brightness
        template_height, template_width = template.shape[:2]
        x, y = max_location
        matched_region = screenshot_cv[y:y+template_height, x:x+template_width]
        gray_region = cv2.cvtColor(matched_region, cv2.COLOR_BGR2GRAY)
        
        return int(np.max(gray_region))

    def _is_transfer_complete(self, screenshot_img, template_path: str, threshold: float = 0.985):
        """
        Check if file transfer operation has completed using template matching.

        Args:
            screenshot_img: PIL Image of the screenshot
            template_path (str): Path to completion indicator template
            threshold (float): Confidence threshold for template matching

        Returns:
            bool: True if transfer appears complete, False otherwise
            
        Raises:
            FileNotFoundError: If template image cannot be loaded
        """
        screenshot_cv = cv2.cvtColor(np.array(screenshot_img), cv2.COLOR_RGB2BGR)
        template = cv2.imread(template_path, cv2.IMREAD_COLOR)
        
        if template is None:
            raise FileNotFoundError(f"Template image not found: {template_path}")
        
        result = cv2.matchTemplate(screenshot_cv, template, cv2.TM_CCOEFF_NORMED)
        _, max_confidence, _, _ = cv2.minMaxLoc(result)
        
        return max_confidence >= threshold
