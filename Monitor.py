import os
import asyncio
from tornado.options import define, options, parse_command_line
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

    def KB(self):
        return self.__translation(self.byte_size)

    def MB(self):
        return self.__translation(self.KB())

    def GB(self):
        return self.__translation(self.MB())


class Email:
    def __init__(self, from_mail, to_mail):
        self.from_mail = from_mail
        self.to_mail = to_mail

    def message(self, mount_point, free_size):
        msg = MIMEMultipart()
        msg['Subject'] = "Внимание! Заканчивается свободное место на разделе!"
        msg['From'] = self.from_mail
        msg['To'] = self.to_mail
        text = "На разделе {mount_point} компьютера {hostname} заканчивается свободное место. " \
               "На текущий момент осталось {free_size} ГБ свободных." \
            .format(mount_point=mount_point, hostname=os.uname().nodename, free_size=free_size)
        msg.attach(MIMEText(text, 'plain'))
        return msg


def main():
    define("mount_point", default="/", help="Точка монтирования, за которой следит скрипт")
    define("sleep_interval", default=20, help="Интервал опроса точки монтирования в секундах")
    define("alarm_limit_gb", default=50,
           help="Лимит свободного дискового пространства в ГБ, при нехватки которого уведомляем ответственных лиц.")
    define("from_mail", default="pacs@viveya.local", help="Почтовый адрес, с которого будут приходить предупреждения.")
    define("to_mail", default="smirnov@viveya.khv.ru", help="Почтовый адрес, на который будут приходить предупреждения")
    define("smtp", default="mail.viveya.khv.ru", help="Почтовый сервер SMTP.")
    parse_command_line()

    if not os.path.exists(options.mount_point):
        raise Exception("Данная точка монтирования не существует!")

    def monitoring(loop):
        mount_point = MountPoint(options.mount_point)
        if mount_point.free_size().GB() < options.alarm_limit_gb:
            email = Email(options.from_mail, options.to_mail)
            with smtplib.SMTP(options.smtp) as smtp:
                smtp.sendmail(email.from_mail, email.to_mail,
                              email.message(options.mount_point, mount_point.free_size().GB()).as_string())
        loop.call_later(options.sleep_interval, monitoring, loop)

    loop = asyncio.get_event_loop()
    try:
        loop.call_soon(monitoring, loop)
        loop.run_forever()
    finally:
        loop.close()


if __name__ == "__main__":
    main()
