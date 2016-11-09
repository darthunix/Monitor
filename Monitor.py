import os
import asyncio
from tornado.options import define, options, parse_command_line


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

    def __translate(self, value):
        return value / self.base

    def bytes(self):
        return self.byte_size

    def KB(self):
        return self.__translate(self.byte_size)

    def MB(self):
        return self.__translate(self.KB())

    def GB(self):
        return self.__translate(self.MB())


def main():
    define("mount_point", default="/", help="Точка монтирования, за которой следит скрипт")
    define("sleep_interval", default=6, help="Интервал опроса точки монтирования в секундах")
    define("alarm_limit_gb", default=50,
           help="Лимит свободного дискового пространства в ГБ, при нехватки которого уведомляем ответственных лиц.")
    parse_command_line()

    if not os.path.exists(options.mount_point):
        raise Exception("Данная точка монтирования не существует!")

    def monitoring(loop):
        mount_point = MountPoint(options.mount_point)
        print(mount_point.free_size().GB())
        if mount_point.free_size().GB() < options.alarm_limit_gb:
            print("Тревога!")
        loop.call_later(options.sleep_interval, monitoring, loop)

    loop = asyncio.get_event_loop()
    try:
        loop.call_soon(monitoring, loop)
        loop.run_forever()
    finally:
        loop.close()


if __name__ == "__main__":
    main()
