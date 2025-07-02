"""
Sony Focus Stacking Image Preview Module

This module provides image processing and preview functionality for focus stacking operations.
It includes focus area detection using gradient analysis and provides a GUI window for 
real-time image preview with focus overlay visualization.
"""

import cv2
import numpy as np
from PIL import Image
import os
import glob
from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt

def detect_focus_areas(image_path):
    """
    Analyze image to detect areas that are in focus using Sobel gradient magnitude.
    
    Args:
        image_path (str): Path to the image file to analyze
        
    Returns:
        tuple: (original_image, focus_map) where focus_map is a normalized gradient magnitude array
        
    Raises:
        ValueError: If image cannot be loaded from the specified path
    """
    img = cv2.imread(image_path, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"Could not load image at {image_path}")
    
    # Convert to grayscale and apply Gaussian blur for noise reduction
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    
    # Calculate gradient magnitude using Sobel operators
    grad_x = cv2.Sobel(blurred, cv2.CV_64F, 1, 0, ksize=3)
    grad_y = cv2.Sobel(blurred, cv2.CV_64F, 0, 1, ksize=3)
    gradient_magnitude = np.sqrt(grad_x ** 2 + grad_y ** 2)
    
    # Normalize to 8-bit range
    focus_map = cv2.normalize(gradient_magnitude, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    
    return img, focus_map

def get_focus_overlay_image(original_img, focus_map):
    """
    Create an overlay visualization combining the original image with focus heatmap.
    
    Args:
        original_img (numpy.ndarray): Original image array from OpenCV
        focus_map (numpy.ndarray): Focus map array with gradient magnitudes
        
    Returns:
        PIL.Image: Combined image with focus overlay as RGB PIL Image
    """
    # Apply color mapping to focus map
    heatmap = cv2.applyColorMap(focus_map, cv2.COLORMAP_HOT)
    
    # Ensure dimensions match
    if heatmap.shape != original_img.shape:
        heatmap = cv2.resize(heatmap, (original_img.shape[1], original_img.shape[0]))
    
    # Blend images and convert to PIL format
    overlayed = cv2.addWeighted(original_img, 0.6, heatmap, 0.4, 0.0)
    overlayed_rgb = cv2.cvtColor(overlayed, cv2.COLOR_BGR2RGB)
    
    return Image.fromarray(overlayed_rgb)

def process_latest_image(directory_path):
    """
    Process the most recently modified image in a directory with focus analysis.
    
    Args:
        directory_path (str): Directory path containing image files
        
    Returns:
        tuple: (focus_overlay_image, focus_map_image) as PIL Images
        
    Raises:
        ValueError: If no image files are found in the directory
    """
    # Search for image files with common extensions
    extensions = ('*.jpg', '*.jpeg', '*.png', '*.bmp', '*.tiff')
    image_files = []
    for ext in extensions:
        image_files.extend(glob.glob(os.path.join(directory_path, ext)))
    
    if not image_files:
        raise ValueError(f"No image files found in {directory_path}")
    
    # Process the most recently modified image
    latest_image = max(image_files, key=os.path.getmtime)
    original_img, focus_map = detect_focus_areas(latest_image)
    overlay_img = get_focus_overlay_image(original_img, focus_map)
    focus_map_img = Image.fromarray(focus_map)
    
    return overlay_img, focus_map_img

class ImagePreviewWindow(QtWidgets.QWidget):
    """
    GUI window for displaying captured images with focus overlay visualization.
    
    Provides real-time preview of images with focus area highlighting using
    gradient magnitude analysis and color mapping.
    """
    
    def __init__(self):
        """Initialize the image preview window with proper sizing and layout."""
        super().__init__()
        self.setWindowTitle("Image Preview")
        self.setFixedSize(500, 400)
        self.setWindowIcon(QtGui.QIcon("assets/images/logo.png"))
        self._create_widgets()
        
    def _create_widgets(self):
        """Create and layout the preview window widgets."""
        layout = QtWidgets.QVBoxLayout(self)
        
        # Main image display area
        self.image_label = QtWidgets.QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("border: 1px solid gray;")
        self.image_label.setText("No image loaded")
        layout.addWidget(self.image_label)
        
        # Status/info display
        self.info_label = QtWidgets.QLabel("Waiting for image...")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.info_label)
        
    def set_image(self, image_path):
        """
        Load and display an image with focus overlay processing.
        
        Args:
            image_path (str): Path to the image file to display
        """
        try:
            if not os.path.exists(image_path):
                self._show_error(f"Image not found: {os.path.basename(image_path)}")
                return
                
            # Process image with focus overlay
            original_img, focus_map = detect_focus_areas(image_path)
            overlay_img = get_focus_overlay_image(original_img, focus_map)
            
            # Convert and display the processed image
            pixmap = self._convert_pil_to_pixmap(overlay_img)
            scaled_pixmap = self._scale_pixmap_to_fit(pixmap)
            
            self.image_label.setPixmap(scaled_pixmap)
            self.info_label.setText(f"Image: {os.path.basename(image_path)}")
            
        except Exception as e:
            self._show_error(f"Error loading image: {str(e)}")

    def _convert_pil_to_pixmap(self, pil_image):
        """
        Convert PIL Image to QPixmap for Qt display.
        
        Args:
            pil_image (PIL.Image): Source PIL image
            
        Returns:
            QPixmap: Converted pixmap for Qt display
        """
        # Ensure RGB format
        if pil_image.mode != 'RGB':
            pil_image = pil_image.convert('RGB')
        
        # Convert to QImage then QPixmap
        width, height = pil_image.size
        rgb_data = pil_image.tobytes('raw', 'RGB')
        qimage = QtGui.QImage(rgb_data, width, height, QtGui.QImage.Format.Format_RGB888)
        
        return QPixmap.fromImage(qimage)

    def _scale_pixmap_to_fit(self, pixmap):
        """
        Scale pixmap to fit within the preview window while maintaining aspect ratio.
        
        Args:
            pixmap (QPixmap): Source pixmap to scale
            
        Returns:
            QPixmap: Scaled pixmap that fits within display area
        """
        max_width, max_height = 480, 350  # Leave margins within 500x400 window
        
        return pixmap.scaled(
            max_width, max_height,
            Qt.AspectRatioMode.KeepAspectRatio, 
            Qt.TransformationMode.SmoothTransformation
        )

    def _show_error(self, message):
        """
        Display an error message in the info label.
        
        Args:
            message (str): Error message to display
        """
        self.info_label.setText(message)

if __name__ == "__main__":
    directory_path = "."
    overlay_image, focus_map_image = process_latest_image(directory_path)
    overlay_image.save('focus_overlay_output.png')
    focus_map_image.save('focus_map_output.png')
