"""
Sony Focus Stacking Controller Module

This module handles the business logic for focus stacking operations, coordinating between
the GUI interface and camera control hardware. It manages the stacking workflow and
provides thread-safe operations for concurrent image capture and focus adjustment.
"""

from stacking.camera_control import ImagingEdgeRemote
from stacking.live_focus_stacking import LiveFocusStacker
from PyQt6 import QtCore, QtWidgets
import threading
import time
import logging
from stacking.logging_config import get_logger

logger = get_logger(__name__)


class StackingWorker(QtCore.QThread):
    """
    Worker thread for executing focus stacking operations.
    
    Handles the complete stacking workflow including focus movement, image capture,
    and automatic focus reversion upon completion or interruption.
    """
    
    # Signal definitions
    log_signal = QtCore.pyqtSignal(str)
    finished_signal = QtCore.pyqtSignal()
    show_pause_stop_signal = QtCore.pyqtSignal()
    hide_pause_stop_signal = QtCore.pyqtSignal()
    show_go_button_signal = QtCore.pyqtSignal()
    hide_go_button_signal = QtCore.pyqtSignal()
    set_pause_button_text_signal = QtCore.pyqtSignal(str)
    close_preview_signal = QtCore.pyqtSignal()
    frame_captured_signal = QtCore.pyqtSignal(int)

    def __init__(self, step_direction, steps_per_frame, num_frames, step_size, camera):
        """
        Initialize the stacking worker.
        
        Args:
            step_direction (str): Direction of focus movement ("near to far" or "far to near")
            steps_per_frame (int): Number of focus steps between each capture
            num_frames (int): Total number of frames to capture
            step_size (str): Step size category ("fine", "normal", or "coarse")
            camera (ImagingEdgeRemote): Camera control instance
        """
        super().__init__()
        self.step_direction = step_direction
        self.steps_per_frame = steps_per_frame
        self.num_frames = num_frames
        self.step_size = step_size
        self.camera = camera
        self._is_paused = False
        self._is_stopped = False
        self._pause_cond = threading.Condition()
        self._total_steps_taken = 0

    def run(self):
        """Execute the focus stacking sequence with proper cleanup."""
        try:
            self._setup_stacking()
            self._execute_stacking_sequence()
        finally:
            self._cleanup_stacking()

    def _setup_stacking(self):
        """Initialize stacking operation and prepare camera."""
        self.show_pause_stop_signal.emit()
        self.hide_go_button_signal.emit()
        self.set_pause_button_text_signal.emit("Pause")
        self.camera.focus()

    def _execute_stacking_sequence(self):
        """Execute the main stacking loop with focus movement and capture."""
        for frame_num in range(self.num_frames):
            if self._check_for_stop():
                return
            
            self._capture_frame(frame_num)
            
            if frame_num < self.num_frames - 1:
                self._move_focus_for_next_frame()
            
            self.camera.wait_for_transfer()

    def _capture_frame(self, frame_num):
        """
        Capture a single frame in the stacking sequence.
        
        Args:
            frame_num (int): Current frame number (0-based)
        """
        self.log_signal.emit(f"Frame {frame_num + 1}/{self.num_frames}: Capturing...")
        logger.debug("Capturing frame %s/%s", frame_num+1, self.num_frames)
        self.camera.capture_image()
        self.camera.wait_for_camera_to_be_ready()
        self.frame_captured_signal.emit(frame_num + 1)

    def _move_focus_for_next_frame(self):
        """Move focus by calculated steps for the next frame."""
        steps = self._calculate_focus_steps()
        self._total_steps_taken += steps
        
        focus_method = (self.camera.focus_far if self.step_direction == "near to far" 
                       else self.camera.focus_near)
        focus_method(steps)

    def _calculate_focus_steps(self):
        """
        Calculate focus steps based on step size and steps per frame.
        
        Returns:
            int: Number of focus steps to move
        """
        step_multipliers = {"fine": 1, "normal": 5, "coarse": 50}
        return self.steps_per_frame * step_multipliers[self.step_size]

    def _check_for_stop(self):
        """
        Check for pause/stop conditions and handle accordingly.
        
        Returns:
            bool: True if operation should stop, False otherwise
        """
        with self._pause_cond:
            while self._is_paused:
                self._pause_cond.wait(0.1)
            if self._is_stopped:
                self.log_signal.emit("Stacking stopped.")
                self._revert_focus()
                return True
        return self._is_stopped

    def _cleanup_stacking(self):
        """Clean up after stacking completion or interruption."""
        if not self._is_stopped:
            self.log_signal.emit("Stacking complete. Returning to starting focus position...")
            self._revert_focus()
            self.log_signal.emit("Focus returned to starting position.")
        
        self.hide_pause_stop_signal.emit()
        self.show_go_button_signal.emit()
        self.set_pause_button_text_signal.emit("Pause")
        self.close_preview_signal.emit()
        self.finished_signal.emit()

    def _revert_focus(self):
        """Revert focus back to the original starting position."""
        if self._total_steps_taken == 0:
            return
        
        # Move focus in opposite direction to return to start
        revert_method = (self.camera.focus_near if self.step_direction == "near to far" 
                        else self.camera.focus_far)
        revert_method(self._total_steps_taken)

    def pause(self):
        """Pause the stacking operation."""
        with self._pause_cond:
            self._is_paused = True
        self.set_pause_button_text_signal.emit("Resume")
        logger.info("Pausing worker")

    def resume(self):
        """Resume the stacking operation."""
        with self._pause_cond:
            self._is_paused = False
            self._pause_cond.notify_all()
        self.set_pause_button_text_signal.emit("Pause")
        logger.info("Resuming worker")

    def stop(self):
        """Stop the stacking operation."""
        with self._pause_cond:
            self._is_stopped = True
            self._pause_cond.notify_all()


class FocusStackingController(QtCore.QObject):
    """
    Main controller coordinating GUI and camera operations.
    
    Manages the lifecycle of stacking operations, handles user interactions,
    and provides status updates to the GUI interface.
    """

    def __init__(self, gui):
        """
        Initialize the controller with GUI and camera instances.
        
        Args:
            gui (FocusStackingApp): Main GUI application instance
        """
        super().__init__()
        self.gui = gui
        try:
            self.camera = ImagingEdgeRemote()
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self.gui,
                "Imaging Edge Remote Not Found",
                "Failed to connect to Sony Imaging Edge Remote.\n"
                "Please make sure the Remote application is open before starting the stack.\n\n"
                f"Error details:\n{e}"
            )
            raise
        self.worker = None
        self.live_stacker = None
        self._render_pending = False  # flag indicating a render should run when current finishes
        self._connect_signals()

    def _connect_signals(self):
        """Connect GUI signals to controller methods."""
        signal_connections = [
            (self.gui.go_button.clicked, self.start_stacking),
            (self.gui.pause_button.clicked, self.toggle_pause),
            (self.gui.stop_button.clicked, self.stop_stacking),
            (self.gui.help_button.clicked, self.show_help)
        ]
        
        for signal, slot in signal_connections:
            signal.connect(slot)

    def start_stacking(self):
        """Initialize and start a new focus stacking operation."""
        config = self._get_stacking_config()
        logger.info("Starting stack with config: %s", config)
        
        self.worker = StackingWorker(
            config['direction'], config['steps_per_frame'], 
            config['frames'], config['step_size'], self.camera
        )
        
        self._connect_worker_signals()
        self.worker.start()

    def _get_stacking_config(self):
        """
        Extract stacking configuration from GUI controls.
        
        Returns:
            dict: Configuration parameters for stacking operation
        """
        return {
            'step_size': self.gui.step_size.currentText(),
            'direction': self.gui.step_direction.currentText(),
            'steps_per_frame': self.gui.steps_per_frame.value(),
            'frames': self.gui.frames.value()
        }

    def _connect_worker_signals(self):
        """Connect worker thread signals to GUI update methods."""
        signal_connections = [
            (self.worker.log_signal, self._log_status),
            (self.worker.show_pause_stop_signal, self.gui.show_pause_stop),
            (self.worker.hide_pause_stop_signal, self.gui.hide_pause_stop),
            (self.worker.show_go_button_signal, self.gui.show_go_button),
            (self.worker.hide_go_button_signal, self.gui.hide_go_button),
            (self.worker.set_pause_button_text_signal, self.gui.set_pause_button_text),
            (self.worker.finished_signal, self._on_worker_finished),
            (self.worker.frame_captured_signal, self._on_frame_captured),
            (self.worker.close_preview_signal, self.gui.close_preview)
        ]
        
        for signal, slot in signal_connections:
            signal.connect(slot)

    def toggle_pause(self):
        """Toggle pause/resume state of the current stacking operation."""
        if not self.worker:
            return
        
        if self.worker._is_paused:
            self.worker.resume()
            self._log_status("Resuming...")
        else:
            self.worker.pause()
            self._log_status("Pausing...")

    def stop_stacking(self):
        """Stop the current stacking operation if running."""
        if self.worker:
            self.worker.stop()

    def show_help(self):
        """Display help information in the status area."""
        self._log_status("Help: Configure your stack and press Go. "
                        "Make sure Imaging Edge Remote is running.")

    def _log_status(self, message):
        """
        Add a status message to the GUI log area.
        
        Args:
            message (str): Status message to display
        """
        self.gui.status_entry.setReadOnly(False)
        self.gui.status_entry.append(message)
        self.gui.status_entry.setReadOnly(True)

    def _on_worker_finished(self):
        """Clean up after worker thread completion."""
        self.worker = None
        logger.info("Worker finished; live render status: %s", self.gui.live_render.isChecked())
        
        # Final render (if not already running)
        if self.gui.live_render.isChecked():
            self._start_live_render()

    def _on_frame_captured(self, frame_index: int):
        """Start live render every 5 captured frames if enabled and not already running."""
        if not self.gui.live_render.isChecked():
            return

        if frame_index % 5 != 0:
            return

        # Prevent overlapping renders
        if self.live_stacker and self.live_stacker.isRunning():
            self._render_pending = True  # schedule another run after current
            logger.debug("Live render already running; marking pending render")
            return

        self._start_live_render()
        logger.debug("Triggered live render on frame %s", frame_index)

    # ------------------------------------------------------------------
    # Live-render management
    # ------------------------------------------------------------------

    def _start_live_render(self):
        """Start a live-render job if directory valid and no current job running."""
        if self.live_stacker and self.live_stacker.isRunning():
            return  # already running

        save_dir = self.gui.save_path.text().strip()
        if not save_dir:
            return

        self.live_stacker = LiveFocusStacker(save_dir, self.gui.program_start_time)
        self.live_stacker.render_finished_signal.connect(self.gui._show_live_render_preview)
        self.live_stacker.log_signal.connect(self._log_status)
        self.live_stacker.finished.connect(self._on_live_render_finished)
        self.live_stacker.start()

    def _on_live_render_finished(self):
        """Handle completion of a live-render job and start pending one if requested."""
        self.live_stacker = None
        if self._render_pending:
            self._render_pending = False
            self._start_live_render() 