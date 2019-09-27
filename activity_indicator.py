'''
Sends a message to a BBC Micro:bit whenever a change occurs in a Smartbox Grid 2, 3 or
Tobii Communicator window.
This is run from the communications device using Python v3.4 or later.
v2.1 looks at top fifth of the grid 2 window for a difference in the number of black pixels
v2.2 works with grid2, grid3 and Tobii communicator
matt.oppenheim@gmail.com
'''

import click
from datetime import datetime
import sys
# ImageGrab is windows only
try:
    from PIL import ImageGrab, ImageStat
except ImportError:
    print('you need to install pillow\npip install pillow')
    sys.exit()
# pythoncom is windows only
try:
    import pythoncom
except ModuleNotFoundError:
    print('you need to download and install pywin3')
    pass
import serial
from serial.tools import list_ports
import time
try:
    import win32gui
except ModuleNotFoundError:
    print('you need to install win32gui\npip install pywin32')
    pass
# use SetProcessDPIAware() in case 100% scaling is not set in windows 8
try:
    from ctypes import windll
except ImportError:
    print('need to run this on Windows')
    pass
user32 = windll.user32
user32.SetProcessDPIAware()
# number of changed pixels to cause an activity trigger
LIMIT = 3
FRACTION = 0.2

# titles of windows to look for activity in


SOFTWARES = ['grid', 'communicator']


def check_fraction(fraction):
    ''' Check that the faction is >0 and <1. '''
    if not 0.01 < fraction < 0.99:
        print('Fraction needs to be between 0.01 and 0.99')
        sys.exit()


def count_black_pixels(image):
    ''' Count the number of black pixels in <image>. '''
    black = 0
    for pixel in image.getdata():
        if pixel == (0, 0, 0):
            black += 1
    return black


def find_mbit_comport():
    ''' Find the port that a microbit is connected to. '''
    ports = list(list_ports.comports())
    for p in ports:
        if (p.pid == 516) and (p.vid == 3368):
            return str(p.device)


def find_hwnd(softwares):
    ''' Find the window id for communication software. '''
    toplist, winlist = [], []

    def _enum_cb(hwnd, results):
        winlist.append((hwnd, win32gui.GetWindowText(hwnd)))
    win32gui.EnumWindows(_enum_cb, toplist)
    for sware in softwares:
        # winlist is a list of tuples (window_id, window title)
        for hwnd, title in winlist:
            if sware in title.lower():
                return hwnd, title
    print('no communications software found for {}'.format(SOFTWARES))
    time.sleep(0.5)


def format_list(in_list):
    str_format = len(in_list) * ' {:.2f}'
    return str_format.format(*in_list)


def image_rms(image):
    ''' Return the RMS sum for image. '''
    return sum(ImageStat.Stat(image).rms)


def get_time():
    ''' Return a formatted time string. '''
    return datetime.now().strftime('%H:%M:%S')


def message_mbit(mbit_port, message):
    ''' Send <message> to the microbit. '''
    mbit_port.write(message)


def serial_connect(serial_port, baud=9600):
    ''' Return a serial port connection. '''
    print('Trying to connect to serial port: {}'.format(serial_port))
    try:
        serial_connection = serial.Serial(serial_port, baud,
            rtscts=True, dsrdtr=True)
        serial_connection.flushInput()
    except Exception as e:
        print('serial_connect error {}'.format(e))
        return None
    print('Serial port {} set up with baud {}'.format(serial_port, baud))
    return serial_connection


@click.command()
@click.option('--limit', default=LIMIT,
    help='Number of changed pixels to trigger event. Default is {}.'
    .format(LIMIT))
@click.option('--fraction', default=FRACTION,
     help='Fraction of screen, from the top, to monitor. Default is {}.'
     .format(FRACTION))
def main(limit, fraction):
    check_fraction(fraction)
    print('limit={} fraction={}'.format(limit, fraction))
    mbit_found = False
    mbit_port = find_mbit_comport()
    if mbit_port:
        print('mbit at port: {}'.format(mbit_port))
        mbit_found = True
        mbit_port = serial_connect(mbit_port)
        message_mbit(mbit_port, b'flash')
    else:
        print('mbit not found')
    old_black = 0
    while True:
        try:
            hwnd, title = find_hwnd(SOFTWARES)
        except TypeError:
            print('no communications software found for {}'.format(SOFTWARES))
            time.sleep(0.5)
            continue
        # bbox is (left, top, right, bottom) with top left as origin
        bbox = win32gui.GetWindowRect(hwnd)
        # grap top fifth of image only
        bbox_topq = (bbox[0], bbox[1], bbox[2], bbox[1] + \
                     int((bbox[3]-bbox[1])*fraction))
        try:
            img = ImageGrab.grab(bbox_topq)
        except OSError as e:
            print('OSError: {}'.format(e))
            continue
        try:
            new_black = count_black_pixels(img)
            # print('{} {} new_black'.format(get_time(), new_black))
        except ZeroDivisionError as e:
            print('ZeroDivisionError: {}'.format(e))
        if abs(new_black - old_black) > limit:
            print('{} Change detected {}'.format(get_time(), title))
            if mbit_found:
                message_mbit(mbit_port, b'flash')
        old_black = new_black
        time.sleep(0.5)
    mbit_port.close()


if __name__ == '__main__':
    main()
