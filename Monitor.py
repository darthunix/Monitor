import os
import asyncio
import argparse
import logging
from logging import DEBUG, INFO, WARNING, ERROR
import smtplib
from email.mime.text import MIMEText
import configparser


class MountPoint:
    def __init__(self, path):
        self.path = path

    def free_size(self):
        stat = os.statvfs(self.path)
        return Size(stat.f_bavail * stat.f_bsize)


class Size:
    def __init__(self, byte_size):
        self.byte_size = byte_size
        self.base = 1024

    def __translation(self, value):
        return round(value / self.base, 1)

    def bytes(self):
        return self.byte_size

    def kb(self):
        return self.__translation(self.byte_size)

    def mb(self):
        return self.__translation(self.kb())

    def gb(self):
        return self.__translation(self.mb())


class Mail:
    def __init__(self, from_mail, to_mail, mount_point, free_size):
        self.from_mail = from_mail
        self.to_mail = to_mail
        self.subject = "Внимание! Заканчивается свободное место на разделе!"
        self.text = "На разделе '{mount_point}' компьютера '{hostname}' заканчивается свободное место. " \
                    "На текущий момент свободно {free_size} ГБ." \
                    .format(mount_point=mount_point, hostname=os.uname().nodename, free_size=free_size)

    def message(self):
        msg = MIMEText(self.text, "plain")
        msg['Subject'] = self.subject
        msg['From'] = self.from_mail
        msg['To'] = self.to_mail
        return msg


class Monitor:
    def __init__(self, settings):
        self.mount_point = settings["mount_point"]
        self.sleep_interval = int(settings["sleep_interval"])
        self.alarm_limit_gb = int(settings["alarm_limit_gb"])
        self.from_mail = settings["from_mail"]
        self.to_mail = settings["to_mail"]
        self.smtp = settings["smtp"]
        self.log_file = settings["log_file"]
        self.log_level = settings["log_level"]

    def run(self):
        if not os.path.exists(self.mount_point):
            message = "Данная точка монтирования не существует!"
            logging.error(message)
            raise Exception(message)

        logging.basicConfig(filename=self.log_file, level=self.log_level,
                            format="%(levelname)-8s [%(asctime)s]  %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

        def monitoring(ioloop):
            mount_point = MountPoint(self.mount_point)
            if mount_point.free_size().gb() < self.alarm_limit_gb:
                with smtplib.SMTP(self.smtp) as smtp:
                    try:
                        mail = Mail(self.from_mail, self.to_mail, mount_point.path, mount_point.free_size().gb())
                        smtp.sendmail(mail.from_mail, mail.to_mail, mail.message().as_string())
                        logging.warning("Отправлено письмо на {to_mail} с содержанием: '{text}'"
                                        .format(to_mail=mail.to_mail, text=mail.text))
                    except Exception as err:
                        logging.error("Ошибка при отправке сообщения о заканчиваюемся свободном месте: {err}"
                                      .format(err=err))

            else:
                logging.debug("Все хорошо. На '{mount_point}' свободно еще {free_size} ГБ."
                              .format(mount_point=mount_point.path, free_size=mount_point.free_size().gb()))
            ioloop.call_later(self.sleep_interval, monitoring, ioloop)

        loop = asyncio.get_event_loop()
        try:
            loop.call_soon(monitoring, loop)
            loop.run_forever()
        finally:
            loop.close()
            logging.info("Программа завершена")


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--conf_file", nargs="?", default="monitor.conf", help="Файл с настройками")
    options = parser.parse_args()

    conf_file = configparser.ConfigParser()
    conf_file.read(options.conf_file)
    config = {}
    for section in conf_file.sections():
        config = {**config, **{key: conf_file[section][key] for key in conf_file[section]}}

    monitor = Monitor(config)
    monitor.run()
