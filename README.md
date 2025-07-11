# 📸 Sony Focus Stacking

![License](https://img.shields.io/badge/License-MIT-blue.svg)
![Python Version](https://img.shields.io/badge/Python-3.10%2B-blue)
![Made with](https://img.shields.io/badge/Made%20with-PyQt6%20%26%20OpenCV-orange)

This application provides a user-friendly interface for focus stacking with Sony cameras, leveraging the Sony Imaging Edge Remote application for camera control. It automates the process of capturing a series of images at different focus points and can provide a live preview of the stacked image.

## ✨ Features

*   **🤖 Automated Focus Stacking:**  Automates the process of capturing a series of images with different focus points.
*   **📺 Live Preview:** (Optional) Provides a live preview of the stacked image as it's being created.
*   **⚙️ Customizable Stacking Parameters:** Allows you to configure the step size, step direction, steps per frame, and the total number of frames.
*   **🖼️ Image Preview:** (Optional) Shows a preview of each image as it's captured.
*   **💾 Settings Persistence:** Saves your settings between sessions.
*   **💻 Cross-Platform:** Built with Python and PyQt6, making it compatible with Windows, macOS, and Linux.

## 📋 Requirements

*   **🐍 Python:** Version 3.10 or higher.
*   **📷 Sony Imaging Edge Remote:** The Sony Imaging Edge Remote application must be installed and running.
*   **📦 Poetry:** This project uses Poetry for dependency management.

## 🚀 Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/M-Enderle/FocusStack.git
    cd FocusStack
    ```

2.  **Download `focus-stack` executable:**
    Download the latest release of `focus-stack` from [https://github.com/PetteriAimonen/focus-stack/releases](https://github.com/PetteriAimonen/focus-stack/releases).
    Extract the contents of the downloaded archive and place the `focus-stack` folder (containing `focus-stack.exe`) in the root of this project.

3.  **Install dependencies using Poetry:**
    ```bash
    poetry install
    ```

## 🛠️ Usage

1.  **Start the application:**
    ```bash
    poetry run python src/stacking/gui.py
    ```

2.  **Configure the stacking parameters:**
    *   **Step size:** Choose between "normal", "fine", and "coarse" for the focus step size.
    *   **Step direction:** Select whether to move the focus from "near to far" or "far to near".
    *   **Steps per frame:** Set the number of focus steps to move between each captured frame.
    *   **Frames:** Specify the total number of frames to capture.

3.  **Configure the output:**
    *   **Preview Images:** Check this box to see a preview of each image as it's captured.
    *   **Live Render:** Check this box to see a live preview of the stacked image as it's being created.
    *   **Save path:** Specify the directory where the captured images will be saved.

4.  **Start the stacking process:**
    *   Click the "Go" button to begin the focus stacking process.
    *   You can pause, resume, or stop the process at any time using the "Pause", "Resume", and "Stop" buttons.

## 🎞️ Live Render

The live render feature provides a preview of the final stacked image while the capture is in progress. It works by running the `focus-stack.exe` executable (included in the repository) on the captured images in the background. The live render will update every 5 frames.

## 🤔 Troubleshooting

*   **"Imaging Edge Remote Not Found" error:** Make sure that the Sony Imaging Edge Remote application is running before you start the focus stacking process.
*   **No images are being captured:** Ensure that your camera is connected to your computer and that the Imaging Edge Remote application can control it.
*   **The live render is not working:** Make sure that the `focus-stack.exe` executable is located in the `focus-stack` directory in the root of the project.

## 📜 License

This project is licensed under the MIT License. See the `LICENSE.txt` file for details.
