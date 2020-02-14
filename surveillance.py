import argparse
import datetime
import json
import logging
import os
import signal
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
        avg_frame = None
        last_capture = datetime.datetime.utcfromtimestamp(0)
        _LOG.info("starting capture")
        self._running = True
        while self._running:
            grabbed, frame = video.read()
            if not grabbed:
                continue
            now = datetime.datetime.now()
            is_motion = False

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (21, 21), 0)

            if avg_frame is None:
                avg_frame = gray.copy().astype("float")
                continue

            # accumulate the weighted average between the current frame and
            # previous frames, then compute the difference between
            # the current frame and running average
            cv2.accumulateWeighted(gray, avg_frame, 0.5)
            frame_delta = cv2.absdiff(gray, cv2.convertScaleAbs(avg_frame))

            # threshold the delta image, dilate the threshold-ed image
            # to fill in holes, then find contours on threshold-ed image
            _, thresh = cv2.threshold(frame_delta, self._config["delta_thresh"], 255, cv2.THRESH_BINARY)
            thresh = cv2.dilate(thresh, None, iterations=2)
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for contour in contours:
                # if the contour is too small, ignore it
                if cv2.contourArea(contour) < self._config["min_area"]:
                    continue
                (x, y, width, height) = cv2.boundingRect(contour)
                cv2.rectangle(frame, (x, y), (x + width, y + height), (0, 255, 0), 2)
                is_motion = True

            if is_motion:
                cv2.putText(frame, "Motion detected", (10, 20),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                if (now - last_capture).total_seconds() >= self._config["min_interval"]:
                    last_capture = now
                    image_path = self._save_image(frame, now)
                    for handler in motion_handlers:
                        handler.handle(image_path, now)

            if self._config["show_video"]:
                cv2.imshow("Camera", frame)
                # break on ESC
                if cv2.waitKey(10) & 0xFF == 27:
                    break

        video.release()
        _LOG.info("capture stopped")

    def stop(self):
        self._running = False

    def _save_image(self, frame, timestamp):
        ymd = timestamp.strftime("%Y-%m-%d")
        base_path = "{}/{}".format(self._config["base_path"], ymd)
        image_ext = self._config["image_ext"]
        file_name = timestamp.strftime("%H-%M-%S-%f")
        image_path = "{}/{}.{}".format(base_path, file_name, image_ext)
        if not os.path.exists(base_path):
            os.makedirs(base_path)
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

    # defaults
    config = {
        "video_device": 0,
        "show_video": True,
        "delta_thresh": 5,
        "framerate": 10,
        "min_area": 5000,
        "min_interval": 10,
        "base_path": "./data",
        "image_ext": "png",
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
