# homewatch

Monitor your home with a Raspberry Pi and a web camera. 

Based on [Home surveillance and motion detection with the Raspberry Pi, Python, OpenCV, and Dropbox][1].

## Prerequisites

- Raspberry Pi 4 Model B
- Python 3.7+
- OpenCV 4.0+

## Installation

1. Follow [Install OpenCV 4 on Raspberry Pi 4 and Raspbian Buster][2] to install OpenCV. I recommend to go with option B - compiling OpenCV from source.
2. Clone the repository: `git clone https://github.com/catalinc/homewatch`

## Quickstart

Edit `config.json` to adjust the configuration. Run the script with `python surveillance.py -c config.json`.

Configuration:

```
{
    // Video capture device id. No need to change if you connected only one webcam to RPi. 
	"video_device": 0, 
    // Show live camera feed. Set to false when running in headless mode.
	"show_video": true,
    // Threshold to compute the absolute difference between current frame and average frame.
	"delta_thresh": 5,
    // FPS
	"framerate": 30,
    // Minimum countour area for detecting motion.
	"min_area": 5000,
    // Minimum interval between two detections (in seconds).
	"min_interval": 5,
    // Where to save the frames containing motion.
	"base_path": "./data",
    // Image type
	"image_ext": "png",
    // Send emails with frames containing motion.
	"email": {
        // Send emails?
		"enabled": false,
        // Email from
		"from": "",
        // Email to
		"to": "",
        // SMTP password in plain text. Consider yourself warned :). 
		"password": "",
        // SMTP host
		"host": "",
        // Minimum interval between emails (in seconds)
		"interval": 30
	}
}
```

[1]: http://www.pyimagesearch.com/2015/06/01/home-surveillance-and-motion-detection-with-the-raspberry-pi-python-and-opencv/
[2]: https://www.pyimagesearch.com/2019/09/16/install-opencv-4-on-raspberry-pi-4-and-raspbian-buster/