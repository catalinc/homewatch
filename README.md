# homewatch

Monitor your home with a Raspberry Pi and a Pi camera.

Based on [Home surveillance and motion detection with the Raspberry Pi, Python, OpenCV, and Dropbox](http://www.pyimagesearch.com/2015/06/01/home-surveillance-and-motion-detection-with-the-raspberry-pi-python-and-opencv/) article.

The script uses a Pi camera to detect motion. Once motion is detected the relevant frames are saved to disk and, optionally, send via email. 

## Prerequisites

- [Raspberry Pi 3 Model B](https://www.raspberrypi.org/products/raspberry-pi-3-model-b/)
- [Pi Camera Module v2](https://www.raspberrypi.org/products/camera-module-v2/)
- Python 2.7
- OpenCV 3.1.0

## Installation

1. Follow [Install guide: Raspberry Pi 3 + Raspbian Jessie + OpenCV 3](http://www.pyimagesearch.com/2016/04/18/install-guide-raspberry-pi-3-raspbian-jessie-opencv-3/) to install OpenCV
2. Clone the repository `git clone https://github.com/catalinc/homewatch`
3. Install dependencies `pip install -r requirements.txt` 

## Quickstart

Edit `config.json` and fill the **email** section. Run the script with `python surveillance.py -c config.json`.