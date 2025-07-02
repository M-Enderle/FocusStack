"""Minimal thread wrapper around *focus-stack.exe* for live-preview rendering."""

from __future__ import annotations

import os
import shutil
import glob
import tempfile
import subprocess
import time
from typing import List, Optional

import logging
from PyQt6 import QtCore
from stacking.logging_config import get_logger

logger = get_logger(__name__)

__all__ = ["LiveFocusStacker"]


class LiveFocusStacker(QtCore.QThread):
    """Qt thread that runs the focus-stack executable and emits the result path."""

    # Emits a str path to the generated stacked image
    render_finished_signal = QtCore.pyqtSignal(str)
    log_signal = QtCore.pyqtSignal(str)

    def __init__(self, save_dir: str, start_time: float, parent: Optional[QtCore.QObject] = None):
        super().__init__(parent)
        self.save_dir = os.path.abspath(save_dir)
        self.start_time = start_time
        self._temp_dir: Optional[str] = None
        self._output_image: Optional[str] = None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _exe_path() -> str:
        """Return absolute path to the bundled focus-stack executable."""
        # Executable shipped in the repository root under focus-stack/focus-stack.exe
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        exe_path = os.path.join(root_dir, "focus-stack", "focus-stack.exe")
        return exe_path

    @staticmethod
    def _filter_images(directory: str, start_time: float) -> List[str]:
        """Return list of image paths in *directory* modified after *start_time*."""
        extensions = (
            "*.jpg", "*.jpeg", "*.png", "*.bmp", "*.tiff",
            "*.JPG", "*.JPEG", "*.PNG", "*.BMP", "*.TIFF",
        )
        paths: List[str] = []
        for ext in extensions:
            paths.extend(glob.glob(os.path.join(directory, ext)))
        filtered = [p for p in paths if os.path.getmtime(p) >= start_time]
        return sorted(filtered, key=lambda p: os.path.getmtime(p))

    # ------------------------------------------------------------------
    # QThread implementation
    # ------------------------------------------------------------------

    def run(self) -> None:  # noqa: D401 – simple description ok
        try:
            logger.info("Preparing images for live render…")
            self.log_signal.emit("[LiveRender] Preparing images…")
            images_to_render = self._filter_images(self.save_dir, self.start_time)
            logger.info("%s images selected for stacking (since start)", len(images_to_render))
            self.log_signal.emit(f"[LiveRender] {len(images_to_render)} images selected for stacking")
            if not images_to_render:
                logger.info("No new images to render – skipping.")
                self.log_signal.emit("[LiveRender] No new images to render – skipping.")
                return

            # Copy images to temp folder so we can use a simple *.JPG glob
            self._temp_dir = tempfile.mkdtemp(prefix="live_render_")
            for src in images_to_render:
                shutil.copy2(src, self._temp_dir)

            logger.debug("Copied %s images to temp dir %s", len(images_to_render), self._temp_dir)
            self.log_signal.emit(f"[LiveRender] Copied {len(images_to_render)} images to temp dir…")

            # Build command
            exe_path = self._exe_path()
            if not os.path.exists(exe_path):
                logger.error("Executable not found: %s", exe_path)
                self.log_signal.emit(f"[LiveRender] Executable not found: {exe_path}")
                return

            cmd = [exe_path, "*.JPG", "--batchsize=32", "--threads=16", "--jpgquality=50"]
            logger.info("Running focus-stack: %s", ' '.join(cmd))
            self.log_signal.emit(f"[LiveRender] Running: {' '.join(cmd)}")
            start = time.time()
            result = subprocess.run(cmd, cwd=self._temp_dir, capture_output=True, text=True)
            duration = time.time() - start

            if result.returncode != 0:
                logger.error("Render failed (exit %s)", result.returncode)
                logger.error(result.stderr[:500])
                self.log_signal.emit(f"[LiveRender] Render failed (exit {result.returncode}).")
                self.log_signal.emit(result.stderr[:500])
                return

            logger.info("Render finished in %.1fs", duration)
            self.log_signal.emit(f"[LiveRender] Render finished in {duration:.1f}s – locating output…")

            # Heuristic: pick newest image created during run that's not one of the originals
            self._output_image = self._locate_output_image(start_time=start)
            if not self._output_image:
                logger.warning("Could not locate output image in %s", self._temp_dir)
                self.log_signal.emit("[LiveRender] Could not find output image.")
                return

            self.render_finished_signal.emit(self._output_image)
            logger.info("Live render output: %s", self._output_image)
            self.log_signal.emit(f"[LiveRender] Output image at {self._output_image}")
        finally:
            # We keep temp dir for debugging; could be removed if needed
            pass

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------

    def _locate_output_image(self, start_time: float) -> Optional[str]:
        """Return path to newest image file created after *start_time* in temp_dir."""
        if not self._temp_dir:
            return None
        candidates: List[str] = []
        for ext in ("*.jpg", "*.jpeg", "*.png", "*.bmp", "*.tiff",
                     "*.JPG", "*.JPEG", "*.PNG", "*.BMP", "*.TIFF"):
            candidates.extend(glob.glob(os.path.join(self._temp_dir, ext)))
        recent_candidates = [p for p in candidates if os.path.getmtime(p) >= start_time]
        if not recent_candidates:
            return None
        return max(recent_candidates, key=os.path.getmtime)
