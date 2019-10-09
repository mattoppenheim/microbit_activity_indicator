'''
Sends a message to a BBC Micro:bit whenever a change occurs in a Smartbox Grid 2, 3 or
Tobii Communicator window.
This is run from the communications device using Python v3.4 or later.
v2.1 looks at top fifth of the grid 2 window for a difference in the number of black pixels
v2.2 works with grid2, grid3 and Tobii communicator
v3.0 uses context manager to enable hot swapping of microbit
matt.oppenheim@gmail.com
'''

import click
from datetime import datetime
import logging
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

logging.basicConfig(
    format='%(asctime)s.%(msecs)03d %(message)s',
    level=logging.INFO,
    datefmt='%H:%M:%S')


class Serial_Con():
    ''' Create a serial connection in a context manager. '''

    def __init__(self, comport, baud=9600):
        self.comport = comport
        self.baud = baud

    
    def __enter__(self):
        ''' Return a serial port connection. '''
        try:
            self.serial_connection = serial.Serial(self.comport, self.baud,
                rtscts=True, dsrdtr=True)
            return self.serial_connection
        except Exception as e:
            logging.info('serial_connect error {}'.format(e))
            return None


    def __exit__(self, *args):
        try:
            self.serial_connection.close()
        except Exception as e:
            logging.info('failed to close serial_connection: {}'.format(e))
        logging.info('Serial_Con closed')


def check_fraction(fraction):
    ''' Check that the faction is >0 and <1. '''
    if not 0.01 < fraction < 0.99:
        logging.info('Fraction needs to be between 0.01 and 0.99')
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
    logging.info('no communications software found for {}'.format(SOFTWARES))
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


def check_software(mbit_serial, old_black, limit, fraction):
    ''' Check software for a change. '''
    try:
        hwnd, title = find_hwnd(SOFTWARES)
    except TypeError:
        ('no communications software found for {}'.format(SOFTWARES))
        return old_black
    # bbox is (left, top, right, bottom) with top left as origin
    bbox = win32gui.GetWindowRect(hwnd)
    # grap top fifth of image only
    bbox_topq = (bbox[0], bbox[1], bbox[2], bbox[1] + \
                int((bbox[3]-bbox[1])*fraction))
    try:
        img = ImageGrab.grab(bbox_topq)
    except OSError as e:
        logging.info('OSError: {}'.format(e))
        return old_black
    try:
        new_black = count_black_pixels(img)
        # logging.info('{} {} new_black'.format(get_time(), new_black))
    except ZeroDivisionError as e:
        logging.info('ZeroDivisionError: {}'.format(e))
        return old_black
    if new_black:
        check_limit(mbit_serial, new_black, old_black, limit)
        return new_black
    else:
        return old_black


def check_limit(mbit_serial, new_black, old_black, limit):
    ''' Deal with new black pixels detected in communication software. '''
    logging.info('new_black: {}, old_black: {}, limit: {}'.format(new_black, old_black, limit))
    if abs(new_black - old_black) > limit:
        logging.info('Change detected')
        if mbit_serial:
            message_mbit(mbit_serial, b'flash')


@click.command()
@click.option('--limit', default=LIMIT,
    help='Number of changed pixels to trigger event. Default is {}.'
    .format(LIMIT))
@click.option('--fraction', default=FRACTION,
     help='Fraction of screen, from the top, to monitor. Default is {}.'
     .format(FRACTION))
def main(limit, fraction):
    logging.info('*** starting find_microbit ***\n')
    check_fraction(fraction)
    logging.info('limit={} fraction={}\n'.format(limit, fraction))
    old_black = 0
    while True:
        logging.info('new cycle')
        mbit_port = find_mbit_comport()
        if mbit_port:
            with Serial_Con(mbit_port) as mbit_serial:
                # occassionally mbit_serial is not created, so is None
                if not mbit_serial:
                    time.sleep(0.5)
                    continue
                mbit_serial.flushInput()
                logging.info('microbit serial port created at: {}'.format(mbit_port))
                old_black = check_software(mbit_serial, old_black, limit, fraction)
        else:
            logging.info('no microbit found')
        time.sleep(0.5)


if __name__ == '__main__':
    main()
