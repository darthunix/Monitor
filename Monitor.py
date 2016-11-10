import os
import asyncio
import argparse
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


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


class Email:

    def __init__(self, from_mail, to_mail):
        self.from_mail = from_mail
        self.to_mail = to_mail

    def message(self, mount_point, free_size):
        msg = MIMEMultipart()
        msg['Subject'] = "Внимание! Заканчивается свободное место на разделе!"
        msg['From'] = self.from_mail
        msg['To'] = self.to_mail
        text = "На разделе '{mount_point}' компьютера '{hostname}' заканчивается свободное место. " \
               "На текущий момент свободно {free_size} ГБ." \
            .format(mount_point=mount_point, hostname=os.uname().nodename, free_size=free_size)
        msg.attach(MIMEText(text, 'plain'))
        return msg


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("mount_point", nargs="?", default="/", help="Точка монтирования, за которой следит скрипт")
    parser.add_argument("sleep_interval", nargs="?", default=20, type=int,
                        help="Интервал опроса точки монтирования в секундах")
    parser.add_argument("alarm_limit_gb", nargs="?", default=50, type=int,
                        help="Лимит свободного дискового пространства в ГБ, "
                             "при нехватки которого уведомляем ответственных лиц.")
    parser.add_argument("from_mail", nargs="?", default="pacs@viveya.local",
                        help="Почтовый адрес, с которого будут приходить предупреждения.")
    parser.add_argument("to_mail", nargs="?", default="smirnov@viveya.khv.ru",
                        help="Почтовый адрес, на который будут приходить предупреждения.")
    parser.add_argument("smtp", nargs="?", default="mail.viveya.khv.ru", help="Почтовый сервер SMTP.")
    options = parser.parse_args()

    if not os.path.exists(options.mount_point):
        raise Exception("Данная точка монтирования не существует!")

    def monitoring(ioloop):
        mount_point = MountPoint(options.mount_point)
        if mount_point.free_size().gb() < options.alarm_limit_gb:
            email = Email(options.from_mail, options.to_mail)
            with smtplib.SMTP(options.smtp) as smtp:
                smtp.sendmail(email.from_mail, email.to_mail,
                              email.message(options.mount_point, mount_point.free_size().gb()).as_string())
        ioloop.call_later(options.sleep_interval, monitoring, ioloop)

    loop = asyncio.get_event_loop()
    try:
        loop.call_soon(monitoring, loop)
        loop.run_forever()
    finally:
        loop.close()
