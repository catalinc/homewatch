import logging
import argparse
import datetime
import json
import time
import os
import signal
import sys
import smtplib
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from picamera import PiCamera
from picamera.exc import PiCameraError
from picamera.array import PiRGBArray
import cv2

_LOG = logging.getLogger(__name__)


class Camera(object):
    """ PiCamera wrapper adding motion detection capabilities """

    def __init__(self, config):
        self._config = config
        self._stop = False

    def capture(self, handlers=()):
        """ Start capture and detect motion """
        camera = PiCamera()
        camera.resolution = tuple(self._config["resolution"])
        camera.framerate = self._config["framerate"]
        raw_capture = PiRGBArray(camera, size=camera.resolution)
        avg_frame = None
        time.sleep(self._config["warmup_time"])
        _LOG.info("capturing...")
        try:
            for frame in camera.capture_continuous(raw_capture, format="bgr", use_video_port=True):
                current_frame = frame.array
                timestamp = datetime.datetime.now()
                motion = False

                # convert it to grayscale and blur it
                gray = cv2.cvtColor(current_frame, cv2.COLOR_BGR2GRAY)
                gray = cv2.GaussianBlur(gray, (21, 21), 0)

                if avg_frame is None:
                    avg_frame = gray.copy().astype("float")
                    raw_capture.truncate(0)
                    continue

                # accumulate the weighted average between the current frame and
                # previous frames, then compute the difference between the current
                # frame and running average
                cv2.accumulateWeighted(gray, avg_frame, 0.5)
                frame_delta = cv2.absdiff(gray, cv2.convertScaleAbs(avg_frame))

                # threshold the delta image, dilate the thresholded image to fill
                # in holes, then find contours on thresholded image
                thresh = cv2.threshold(frame_delta, self._config["delta_thresh"], 255,
                                       cv2.THRESH_BINARY)[1]
                thresh = cv2.dilate(thresh, None, iterations=2)
                _, countours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL,
                                                   cv2.CHAIN_APPROX_SIMPLE)

                for contour in countours:
                    # if the contour is too small, ignore it
                    if cv2.contourArea(contour) < self._config["min_area"]:
                        continue

                    # compute the bounding box for the contour and draw it on
                    # the frame
                    (x_start, y_start, width, height) = cv2.boundingRect(contour)
                    cv2.rectangle(current_frame, (x_start, y_start),
                                  (x_start + width, y_start + height), (0, 255, 0), 2)
                    motion = True

                cv2.putText(current_frame,
                            timestamp.strftime("%A %d %B %Y %I:%M:%S%p"),
                            (10, current_frame.shape[0] - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 255), 1)
                if motion:
                    cv2.putText(current_frame, "Motion detected", (10, 20),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                    image_path = self._write_image(current_frame, timestamp)
                    for handler in handlers:
                        handler.handle(image_path, timestamp)

                if self._config["show_video"]:
                    cv2.imshow("Camera Feed", current_frame)
                    cv2.waitKey(1) & 0xFF

                # clear the stream in preparation for the next frame
                raw_capture.truncate(0)
                if self._stop:
                    break
        except PiCameraError as ex:
            _LOG.error("camera error: %s", ex)
        _LOG.info("capture stopped")

    def stop(self):
        """ Stop capture """
        self._stop = True

    def _write_image(self, frame, timestamp):
        base_path = self._config["base_path"]
        if not os.path.exists(base_path):
            os.makedirs(base_path)
        image_path = "{}/{}.png".format(base_path,
                                        timestamp.strftime("%Y-%m-%d-%H-%M-%S-%f"))
        cv2.imwrite(image_path, frame)
        _LOG.info("motion detected and recorded to '%s'", image_path)
        return image_path


class EmailHandler(object):
    """ Motion handler for sending images via email """

    def __init__(self, config):
        self._config = config
        interval = self._config['email']['interval']
        self._last_time = datetime.datetime.now() - datetime.timedelta(seconds=interval)

    def handle(self, image_path, timestamp):
        """ Send email when motion is detected """
        interval = self._config['email']['interval']
        elapsed = timestamp - self._last_time
        if elapsed.total_seconds() >= interval:
            from_addr = self._config['email']['from']
            password = self._config['email']['password']
            host = self._config['email']['host']
            to_addrs = self._config['email']['to']
            subject = "Motion detected on %s" % timestamp.strftime(
                "%A %d %B %Y %I:%M:%S %p")

            message = MIMEMultipart()
            message['Subject'] = subject
            message['From'] = from_addr
            message['To'] = to_addrs
            text = MIMEText(subject)
            message.attach(text)
            with open(image_path, 'rb') as image_file:
                image = MIMEImage(image_file.read())
                message.attach(image)
                try:
                    server = smtplib.SMTP(host)
                    server.ehlo()
                    server.starttls()
                    server.login(from_addr, password)
                    server.sendmail(from_addr, to_addrs, message.as_string())
                    server.quit()
                    self._last_time = timestamp
                    _LOG.info("email sent with subject '%s'", subject)
                except smtplib.SMTPException as ex:
                    _LOG.error("email error: %s", ex)


def _main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--configuration", required=True,
                        help="path to the configuration file")
    args = parser.parse_args()

    logging.basicConfig(stream=sys.stdout, level=logging.INFO,
                        format="%(asctime)s - %(levelname)s - %(message)s")

    with open(args.configuration) as conf_file:
        config = json.load(conf_file)
        camera = Camera(config)

        def _exit_handler(signal, frame):
            camera.stop()
        signal.signal(signal.SIGINT, _exit_handler)
        signal.signal(signal.SIGTERM, _exit_handler)

        handlers = []
        if config['email']['enabled']:
            handlers.append(EmailHandler(config))
        camera.capture(handlers=handlers)

if __name__ == "__main__":
    _main()
