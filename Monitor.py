import os
import asyncio
import argparse
import logging
from logging import DEBUG, INFO, WARNING, ERROR
import smtplib
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


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("-m", "--mount_point", nargs="?", default="/",
                        help="Точка монтирования, за которой следит скрипт")
    parser.add_argument("-i", "--sleep_interval", nargs="?", default=60, type=int,
                        help="Интервал опроса точки монтирования в секундах")
    parser.add_argument("-a", "--alarm_limit_gb", nargs="?", default=50, type=int,
                        help="Лимит свободного дискового пространства в ГБ, "
                             "при нехватки которого уведомляем ответственных лиц")
    parser.add_argument("-f", "--from_mail", nargs="?", default="pacs@viveya.local",
                        help="Почтовый адрес, с которого будут приходить предупреждения")
    parser.add_argument("-t", "--to_mail", nargs="?", default="zabbix@viveya.khv.ru",
                        help="Почтовый адрес, на который будут приходить предупреждения")
    parser.add_argument("-s", "--smtp", nargs="?", default="mail.viveya.khv.ru", help="Адрес почтового сервера SMTP")
    parser.add_argument("-o", "--log_file", nargs="?", default="/tmp/monitor.log", metavar='OUTPUT_LOG_FILE',
                        help="Расположение лог файл скрипта")
    parser.add_argument("-l", "--log_level", nargs="?", default=INFO, choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        help="Уровень логирования скрипта")
    options = parser.parse_args()

    if not os.path.exists(options.mount_point):
        error_message = "Данная точка монтирования не существует!"
        logging.error(error_message)
        raise Exception(error_message)

    logging.basicConfig(filename=options.log_file, level=options.log_level,
                        format="%(levelname)-8s [%(asctime)s]  %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    def monitoring(ioloop):
        mount_point = MountPoint(options.mount_point)
        if mount_point.free_size().gb() < options.alarm_limit_gb:
            with smtplib.SMTP(options.smtp) as smtp:
                try:
                    mail = Mail(options.from_mail, options.to_mail, mount_point.path, mount_point.free_size().gb())
                    smtp.sendmail(mail.from_mail, mail.to_mail, mail.message().as_string())
                    logging.warning("Отправлено письмо на {to_mail} с содержанием: '{text}'"
                                    .format(to_mail=mail.to_mail, text=mail.text))
                except Exception as err:
                    logging.error("Ошибка при отправке сообщения о заканчиваюемся свободном месте: {err}"
                                  .format(err=err))

        else:
            logging.debug("Все хорошо. На '{mount_point}' свободно еще {free_size} ГБ."
                          .format(mount_point=mount_point.path, free_size=mount_point.free_size().gb()))
        ioloop.call_later(options.sleep_interval, monitoring, ioloop)

    loop = asyncio.get_event_loop()
    try:
        loop.call_soon(monitoring, loop)
        loop.run_forever()
    finally:
        loop.close()
        logging.info("Программа завершена")
