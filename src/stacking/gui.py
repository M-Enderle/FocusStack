"""
Sony Focus Stacking Application - Main GUI Module

This module provides the main graphical user interface for the Sony Focus Stacking application.
It handles user input, settings persistence, and coordinates with the controller for camera operations.
"""

from PyQt6 import QtWidgets, QtCore, QtGui
from stacking.controller import FocusStackingController
import os
import time
import glob
import json
import logging
from stacking.logging_config import get_logger

logger = get_logger(__name__)


class FocusStackingApp(QtWidgets.QWidget):
    """
    Main application window for Sony Focus Stacking.
    
    Provides controls for configuring focus stacking parameters, managing settings persistence,
    and displaying real-time image previews during capture sessions.
    """
    
    def __init__(self):
        """Initialize the application window and load saved settings."""
        super().__init__()
        self.setWindowTitle("Sony Focus Stacking")
        self.setWindowIcon(QtGui.QIcon("logo.png"))
        self.setFixedSize(320, 320)
        
        # Timestamp used for filtering images in live render
        self.program_start_time = time.time()
        
        self._settings_file = "settings.json"
        self._last_shown_image = None
        self.image_preview_window = None
        self.live_render_window = None
        
        self._create_widgets()
        self._setup_image_polling()
        self._load_settings()
        logger.info("Initialized GUI window")

    def _create_widgets(self):
        """Create and layout all GUI widgets with signal connections."""
        layout = QtWidgets.QGridLayout(self)
        
        # Create controls with automatic settings saving
        controls = [
            ("Step size", self._create_combo(["normal", "fine", "coarse"])),
            ("Step direction", self._create_combo(["near to far", "far to near"])),
            ("Steps per frame", self._create_slider(1, 10, 3)),
            ("Frames", self._create_spinbox(1, 999, 10)),
        ]
        
        for i, (label, widget) in enumerate(controls):
            layout.addWidget(QtWidgets.QLabel(label), i, 0)
            layout.addWidget(widget, i, 1)
        
        # Preview checkbox and save path
        self._create_preview_controls(layout)
        
        # Status display
        self.status_entry = QtWidgets.QTextEdit()
        self.status_entry.setReadOnly(True)
        self.status_entry.setFixedHeight(60)
        layout.addWidget(self.status_entry, 6, 0, 1, 2)
        
        # Control buttons
        self._create_buttons(layout)
        
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)

    def _create_combo(self, items):
        """Create a combobox with items and auto-save connection."""
        combo = QtWidgets.QComboBox()
        combo.addItems(items)
        combo.currentTextChanged.connect(self._save_settings)
        return combo

    def _create_slider(self, min_val, max_val, default):
        """Create a slider with range and auto-save connection."""
        slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        slider.setRange(min_val, max_val)
        slider.setValue(default)
        slider.setTickInterval(1)
        slider.setTickPosition(QtWidgets.QSlider.TickPosition.TicksBelow)
        slider.valueChanged.connect(self._save_settings)
        return slider

    def _create_spinbox(self, min_val, max_val, default):
        """Create a spinbox with range and auto-save connection."""
        spinbox = QtWidgets.QSpinBox()
        spinbox.setRange(min_val, max_val)
        spinbox.setValue(default)
        spinbox.valueChanged.connect(self._save_settings)
        return spinbox

    def _create_preview_controls(self, layout):
        """Create preview checkbox and save path controls."""
        # Preview checkbox
        preview_layout = QtWidgets.QHBoxLayout()
        preview_layout.addWidget(QtWidgets.QLabel("Preview Images"))
        self.preview_images = QtWidgets.QCheckBox()
        self.preview_images.setChecked(True)
        self.preview_images.stateChanged.connect(self._save_settings)
        self.preview_images.stateChanged.connect(self._toggle_save_path_visibility)
        preview_layout.addWidget(self.preview_images)
        # Live render checkbox
        preview_layout.addWidget(QtWidgets.QLabel("Live Render"))
        self.live_render = QtWidgets.QCheckBox()
        self.live_render.setChecked(False)
        self.live_render.stateChanged.connect(self._save_settings)
        preview_layout.addWidget(self.live_render)
        layout.addLayout(preview_layout, 4, 0, 1, 2)
        
        # Save path
        self.save_path = QtWidgets.QLineEdit(os.path.expanduser("~/Pictures"))
        self.save_path.textChanged.connect(self._save_settings)
        layout.addWidget(self.save_path, 5, 0, 1, 2)
        
        # Assign widget references for settings
        self.step_size = layout.itemAtPosition(0, 1).widget()
        self.step_direction = layout.itemAtPosition(1, 1).widget()
        self.steps_per_frame = layout.itemAtPosition(2, 1).widget()
        self.frames = layout.itemAtPosition(3, 1).widget()

    def _create_buttons(self, layout):
        """Create control buttons with proper sizing and visibility."""
        button_layout = QtWidgets.QHBoxLayout()
        
        buttons = [
            ("Go", 100, True),
            ("Pause", 70, False),
            ("Stop", 70, False),
            ("?", 50, True)
        ]
        
        for text, width, visible in buttons:
            button = QtWidgets.QPushButton(text)
            button.setFixedSize(width, 30)
            if not visible:
                button.hide()
            button_layout.addWidget(button)
        
        # Assign button references
        self.go_button = button_layout.itemAt(0).widget()
        self.pause_button = button_layout.itemAt(1).widget()
        self.stop_button = button_layout.itemAt(2).widget()
        self.help_button = button_layout.itemAt(3).widget()
        
        layout.addLayout(button_layout, 7, 0, 1, 2)

    def _setup_image_polling(self):
        """Initialize continuous image polling for preview updates."""
        self._polling_timer = QtCore.QTimer()
        self._polling_timer.timeout.connect(self._check_for_new_images)
        self._polling_timer.start(1000)
        logger.debug("Started image polling timer")

    def _check_for_new_images(self):
        """Check for recently captured images and update preview if enabled."""
        if not self.preview_images.isChecked():
            return
        
        try:
            save_dir = self.save_path.text().strip()
            if not save_dir or not os.path.exists(save_dir):
                return
            
            # Find recent images (last 30 seconds)
            extensions = ['*.jpg', '*.jpeg', '*.png', '*.bmp', '*.tiff'] * 2  # Include uppercase
            extensions[5:] = [ext.upper() for ext in extensions[:5]]
            
            all_images = []
            for ext in extensions:
                all_images.extend(glob.glob(os.path.join(save_dir, ext)))
            
            if not all_images:
                return
            
            # Filter by modification time and get latest
            current_time = time.time()
            recent_images = [(img, os.path.getmtime(img)) for img in all_images 
                           if current_time - os.path.getmtime(img) <= 30]
            
            if recent_images and (latest_image := max(recent_images, key=lambda x: x[1])[0]) != self._last_shown_image:
                self._show_image_preview(latest_image)
                self._last_shown_image = latest_image
        except:
            pass
        else:
            logger.debug("Checked for new images, latest shown: %s", self._last_shown_image)

    def _show_image_preview(self, image_path):
        """
        Display image preview window with focus overlay.
        
        Args:
            image_path (str): Path to the image file to display
        """
        try:
            if self.image_preview_window is None:
                from stacking.image_preview import ImagePreviewWindow
                self.image_preview_window = ImagePreviewWindow()
                # Position relative to main window
                pos = self.pos()
                self.image_preview_window.move(pos.x() + self.width() + 10, pos.y())
            
            self.image_preview_window.set_image(image_path)
            self.image_preview_window.show()
            logger.debug("Displayed image preview: %s", image_path)
        except:
            pass

    def _get_default_settings(self):
        """Get default application settings."""
        return {
            "step_size": "normal",
            "step_direction": "near to far",
            "steps_per_frame": 3,
            "frames": 10,
            "preview_images": True,
            "live_render": False,
            "save_path": os.path.expanduser("~/Pictures")
        }

    def _save_settings(self):
        """Save current GUI settings to JSON file."""
        try:
            settings = {
                "step_size": self.step_size.currentText(),
                "step_direction": self.step_direction.currentText(),
                "steps_per_frame": self.steps_per_frame.value(),
                "frames": self.frames.value(),
                "preview_images": self.preview_images.isChecked(),
                "live_render": self.live_render.isChecked(),
                "save_path": self.save_path.text()
            }
            
            with open(self._settings_file, 'w') as f:
                json.dump(settings, f, indent=2)
        except:
            pass

    def _load_settings(self):
        """Load and apply settings from JSON file."""
        try:
            settings = self._get_default_settings()
            if os.path.exists(self._settings_file):
                with open(self._settings_file, 'r') as f:
                    settings.update(json.load(f))
            else:
                self._save_settings()
            
            # Temporarily disconnect signals during loading
            self._disconnect_settings_signals()
            
            # Apply settings
            widgets = [self.step_size, self.step_direction, self.steps_per_frame, 
                      self.frames, self.preview_images, self.live_render, self.save_path]
            values = [settings["step_size"], settings["step_direction"], 
                     settings["steps_per_frame"], settings["frames"],
                     settings["preview_images"], settings["live_render"], settings["save_path"]]
            
            for widget, value in zip(widgets, values):
                if hasattr(widget, 'findText'):
                    index = widget.findText(value)
                    if index >= 0:
                        widget.setCurrentIndex(index)
                elif hasattr(widget, 'setValue'):
                    widget.setValue(value)
                elif hasattr(widget, 'setChecked'):
                    widget.setChecked(value)
                elif hasattr(widget, 'setText'):
                    widget.setText(value)
            
            self._reconnect_settings_signals()
            self._toggle_save_path_visibility()
        except:
            pass

    def _disconnect_settings_signals(self):
        """Temporarily disconnect settings signals to avoid save during load."""
        signals = [
            (self.step_size.currentTextChanged, self._save_settings),
            (self.step_direction.currentTextChanged, self._save_settings),
            (self.steps_per_frame.valueChanged, self._save_settings),
            (self.frames.valueChanged, self._save_settings),
            (self.preview_images.stateChanged, self._save_settings),
            (self.live_render.stateChanged, self._save_settings),
            (self.save_path.textChanged, self._save_settings)
        ]
        for signal, slot in signals:
            signal.disconnect(slot)

    def _reconnect_settings_signals(self):
        """Reconnect settings signals after loading."""
        self.step_size.currentTextChanged.connect(self._save_settings)
        self.step_direction.currentTextChanged.connect(self._save_settings)
        self.steps_per_frame.valueChanged.connect(self._save_settings)
        self.frames.valueChanged.connect(self._save_settings)
        self.preview_images.stateChanged.connect(self._save_settings)
        self.preview_images.stateChanged.connect(self._toggle_save_path_visibility)
        self.live_render.stateChanged.connect(self._save_settings)
        self.live_render.stateChanged.connect(self._toggle_save_path_visibility)
        self.save_path.textChanged.connect(self._save_settings)

    def _toggle_save_path_visibility(self):
        """Show/hide save path.

        The path field must remain visible if *either* Preview Images or Live Render is
        enabled so the directory can be configured for downstream processing.
        """
        self.save_path.setVisible(self.preview_images.isChecked() or self.live_render.isChecked())

    def _close_image_preview(self):
        """Close and cleanup image preview window."""
        if self.image_preview_window is not None:
            self.image_preview_window.close()
            self.image_preview_window = None

    # ------------------------------------------------------------------
    # Live render preview helpers
    # ------------------------------------------------------------------

    def _show_live_render_preview(self, image_path):
        """Display stacked image preview on the *left* side of the main window."""
        try:
            # Close any previous preview to ensure fresh window and avoid stale content
            if self.live_render_window is not None:
                self.live_render_window.close()
                self.live_render_window = None

            if self.live_render_window is None:
                from PyQt6 import QtGui  # local import to avoid circular
                self.live_render_window = QtWidgets.QWidget()
                self.live_render_window.setWindowTitle("Live Render Preview")
                self.live_render_window.setFixedSize(500, 400)
                self.live_render_window.setWindowIcon(QtGui.QIcon("logo.png"))

                v_layout = QtWidgets.QVBoxLayout(self.live_render_window)
                self.live_render_label = QtWidgets.QLabel()
                self.live_render_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                self.live_render_label.setStyleSheet("border: 1px solid gray;")
                v_layout.addWidget(self.live_render_label)

            pixmap = QtGui.QPixmap(image_path)
            if pixmap.isNull():
                return
            scaled = pixmap.scaled(480, 350, QtCore.Qt.AspectRatioMode.KeepAspectRatio, QtCore.Qt.TransformationMode.SmoothTransformation)
            self.live_render_label.setPixmap(scaled)

            # Position window left of main window
            pos = self.pos()
            self.live_render_window.move(pos.x() - self.live_render_window.width() - 10, pos.y())
            self.live_render_window.show()
            logger.debug("Displayed live render preview: %s", image_path)
        except Exception:
            pass

    def _close_live_render_preview(self):
        """Close live render preview window if open."""
        if self.live_render_window is not None:
            self.live_render_window.close()
            self.live_render_window = None

    # Public API methods for controller
    def show_pause_stop(self):
        """Show pause and stop buttons during stacking operation."""
        self.pause_button.show()
        self.stop_button.show()

    def hide_pause_stop(self):
        """Hide pause and stop buttons when not stacking."""
        self.pause_button.hide()
        self.stop_button.hide()

    def show_go_button(self):
        """Show the go button."""
        self.go_button.show()

    def hide_go_button(self):
        """Hide the go button during stacking."""
        self.go_button.hide()

    def set_pause_button_text(self, text):
        """
        Set the text of the pause button.
        
        Args:
            text (str): Button text ("Pause" or "Resume")
        """
        self.pause_button.setText(text)

    def close_preview(self):
        """Close image preview when stacking stops."""
        self._close_image_preview()
        self._close_live_render_preview()

    def close_live_render(self):
        """Close live render window (controller hook)."""
        self._close_live_render_preview()

    def closeEvent(self, event):
        """Handle application shutdown with cleanup."""
        if hasattr(self, '_polling_timer'):
            self._polling_timer.stop()
        self._close_image_preview()
        self._close_live_render_preview()
        self._save_settings()
        event.accept()


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    window = FocusStackingApp()
    controller = FocusStackingController(window)
    window.show()
    sys.exit(app.exec()) 