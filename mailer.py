import datetime
import logging
import smtplib
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

_LOG = logging.getLogger(__name__)


class Mailer(object):
    def __init__(self, config):
        self._config = config
        self._last_send = datetime.datetime.utcfromtimestamp(0)

    def send_mail(self, image_path, timestamp):
        interval = self._config['email']['interval']
        if (timestamp - self._last_send).total_seconds() >= interval:
            from_addr = self._config['email']['from']
            password = self._config['email']['password']
            host = self._config['email']['host']
            to_addr = self._config['email']['to']
            subject = "Motion detected at %s" % timestamp.strftime(
                "%A %d %B %Y %I:%M:%S %p")

            message = MIMEMultipart()
            message['Subject'] = subject
            message['From'] = from_addr
            message['To'] = to_addr
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
                    server.sendmail(from_addr, to_addr, message.as_string())
                    server.quit()
                    self._last_send = timestamp
                    _LOG.info("email sent: %s", subject)
                except smtplib.SMTPException as ex:
                    _LOG.error("email error: %s", ex)
