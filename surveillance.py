import argparse
import datetime
import json
import logging
import os
import signal
import threading
import time
import cv2
import sys

from mailer import Mailer

_LOG = logging.getLogger(__name__)


class Camera(object):
    def __init__(self, config):
        self._config = config
        self._running = False

    def start(self, motion_handlers=()):
        _LOG.info("opening device")
        video = cv2.VideoCapture(self._config["video_device"])
        video.set(cv2.CAP_PROP_FPS, self._config["framerate"])
        video.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        avg_frame = None
        last_capture = datetime.datetime.utcfromtimestamp(0)
        frame_count = 0
        skip_frames = self._config.get("skip_frames", 2)
        consecutive_failures = 0

        _LOG.info("starting capture")
        self._running = True
        while self._running:
            grabbed, frame = video.read()
            if not grabbed:
                consecutive_failures += 1
                if consecutive_failures >= 10:
                    _LOG.warning("camera unavailable, retrying in 5s...")
                    video.release()
                    time.sleep(5)
                    video = cv2.VideoCapture(self._config["video_device"])
                    video.set(cv2.CAP_PROP_FPS, self._config["framerate"])
                    video.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    avg_frame = None
                    consecutive_failures = 0
                continue
            consecutive_failures = 0

            frame_count += 1
            if frame_count % skip_frames != 0:
                continue

            now = datetime.datetime.now()
            is_motion = False

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # Downscale before heavy processing; scale contours back for display
            h, w = gray.shape[:2]
            proc_w = self._config.get("process_width", 500)
            proc_h = int(h * proc_w / w)
            scale_x, scale_y = w / proc_w, h / proc_h
            gray = cv2.resize(gray, (proc_w, proc_h))

            gray = cv2.GaussianBlur(gray, (11, 11), 0)

            if avg_frame is None:
                avg_frame = gray.copy().astype("float")
                continue

            cv2.accumulateWeighted(gray, avg_frame, 0.1)
            frame_delta = cv2.absdiff(gray, cv2.convertScaleAbs(avg_frame))

            _, thresh = cv2.threshold(frame_delta, self._config["delta_thresh"], 255, cv2.THRESH_BINARY)
            thresh = cv2.dilate(thresh, kernel, iterations=2)
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            scaled_min_area = self._config["min_area"] / (scale_x * scale_y)
            for contour in contours:
                if cv2.contourArea(contour) < scaled_min_area:
                    continue
                (x, y, width, height) = cv2.boundingRect(contour)
                x1, y1 = int(x * scale_x), int(y * scale_y)
                x2, y2 = int((x + width) * scale_x), int((y + height) * scale_y)
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                is_motion = True

            if is_motion:
                cv2.putText(frame, "Motion detected", (10, 20),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                if (now - last_capture).total_seconds() >= self._config["min_interval"]:
                    last_capture = now
                    frame_copy = frame.copy()
                    threading.Thread(
                        target=self._save_and_notify,
                        args=(frame_copy, now, motion_handlers),
                        daemon=True
                    ).start()

            if self._config["show_video"]:
                cv2.imshow("Camera", frame)
                if cv2.waitKey(1) & 0xFF == 27:
                    break
                if cv2.getWindowProperty("Camera", cv2.WND_PROP_VISIBLE) < 1:
                    break

        video.release()
        _LOG.info("capture stopped")

    def stop(self):
        self._running = False

    def _save_and_notify(self, frame, timestamp, handlers):
        image_path = self._save_image(frame, timestamp)
        for handler in handlers:
            handler.handle(image_path, timestamp)

    def _save_image(self, frame, timestamp):
        ymd = timestamp.strftime("%Y-%m-%d")
        base_path = "{}/{}".format(self._config["base_path"], ymd)
        image_ext = self._config["image_ext"]
        file_name = timestamp.strftime("%H-%M-%S-%f")
        image_path = "{}/{}.{}".format(base_path, file_name, image_ext)
        os.makedirs(base_path, exist_ok=True)
        cv2.imwrite(image_path, frame)
        _LOG.info("motion recorded to %s", image_path)
        return image_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--configuration", required=False,
                        help="path to the configuration file")
    args = parser.parse_args()

    logging.basicConfig(stream=sys.stdout, level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] - %(message)s")

    config = {
        "video_device": 0,
        "show_video": True,
        "delta_thresh": 5,
        "framerate": 30,
        "skip_frames": 2,
        "min_area": 5000,
        "min_interval": 10,
        "process_width": 500,
        "base_path": "./data",
        "image_ext": "jpg",
        "email": {
            "enabled": False
        }
    }
    if args.configuration:
        with open(args.configuration) as conf_file:
            config.update(json.load(conf_file))

    camera = Camera(config)

    def _exit_handler(signal_code, frame):
        camera.stop()
        cv2.destroyAllWindows()

    signal.signal(signal.SIGINT, _exit_handler)
    signal.signal(signal.SIGTERM, _exit_handler)

    handlers = []
    if config['email']['enabled']:
        handlers.append(Mailer(config))
    camera.start(motion_handlers=handlers)


if __name__ == "__main__":
    main()
