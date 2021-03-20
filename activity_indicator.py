'''
Sends a message to a BBC Micro:bit whenever a change occurs in a Smartbox Grid 2, 3 or
Tobii Communicator window.
This is run from the communications device using Python v3.4 or later.
v2.1 looks at top fifth of the grid 2 window for a difference in the number of black pixels
v2.2 works with grid2, grid3 and Tobii communicator
v3.0 uses context manager to enable hot swapping of microbit
v3.1 improved finding grid window and hot swapping of microbit
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
BAUD = 9600
PID_MICROBIT = 516
# software that requires this script to run in Administrator mode
VID_MICROBIT = 3368

# titles of windows to look for activity in

COM_SOFTWARE = ['grid', 'communicator']
# extra windows that are not visible can be created by e.g. Grid 3
IGNORE = ['grid 3.exe', 'users']
TIMEOUT = 0.1

logging.basicConfig(
    format='%(asctime)s.%(msecs)03d %(message)s',
    level=logging.INFO,
    datefmt='%H:%M:%S')


def singleton(cls, *args):
    ''' Singleton pattern. '''
    instances = {}
    def getinstance(*args):
        if cls not in instances:
            instances[cls] = cls(*args)
        return instances[cls]
    return getinstance

@singleton
class Serial_Con():
    ''' Create a serial connection in a context manager. '''

    def __init__(self, comport, baud=BAUD):
        self.comport = comport
        self.baud = baud


    def __enter__(self):
        ''' Return a serial port connection. '''
        try:
            self.serial_connection = serial.Serial(self.comport, self.baud,
                rtscts=True, dsrdtr=True)
            logging.debug('created Serial_Con on: {}'.format(self.comport))
            return self.serial_connection
        except Exception as e:
            logging.info('serial_connect error {}'.format(e))
            return None


    def __exit__(self, *args):
        try:
            self.serial_connection.close()
        except Exception as e:
            logging.info('failed to close serial_connection: {}'.format(e))
        logging.info('serial connection closed')


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


def find_comport(pid, vid, baud):
    ''' Open the serial port with device with <pid> and <vid> connected. '''
    ser_port = serial.Serial(timeout = TIMEOUT)
    ser_port.baudrate = baud
    ports = list(list_ports.comports())
    logging.debug('scanning ports')
    for p in ports:
        logging.debug('pid: {} vid: {}'.format(p.pid, p.vid))
        if (p.pid == pid) and (p.vid == vid):
            logging.debug('found target device pid: {} vid: {} port: {}'.format(p.pid, p.vid, p.device))
            return str(p.device)
    return None


def get_comport(pid, vid, baud):
    ''' Get a serial connection to pid, vid. '''
    comport = find_comport(pid, vid, baud)
    while True:
        if comport:
            return comport
        comport = find_comport(pid, vid, baud)
        time.sleep(0.5)


def find_window_handle(com_software=COM_SOFTWARE, ignore=IGNORE):
    ''' Find the window for communication software. '''
    toplist, winlist = [], []

    def _enum_cb(window_handle, results):
        winlist.append((window_handle, win32gui.GetWindowText(window_handle)))

    win32gui.EnumWindows(_enum_cb, toplist)
    for sware in com_software:
        # winlist is a list of tuples (window_id, window title)
        logging.debug('items in ignore: {}'.format([item.lower() for item in ignore]))
        for window_handle, title in winlist:
            #logging.debug('window_handle: {}, title: {}'.format(window_handle, title))
            if sware in title.lower() and not any (x in title.lower() for x in ignore):
                # logging.debug('found title: {}'.format(title))
                return window_handle
    logging.info('no communications software found for {}'.format(com_software))
    time.sleep(0.5)


def format_list(in_list):
    str_format = len(in_list) * ' {:.2f}'
    return str_format.format(*in_list)


def get_time():
    ''' Return a formatted time string. '''
    return datetime.now().strftime('%H:%M:%S')


def message_mbit(mbit_port, message):
    ''' Send <message> to the microbit. '''
    mbit_port.write(message)


def get_window_top(fraction, software=COM_SOFTWARE):
    ''' Find the top of the window containing target software. '''
    try:
        window_handle = find_window_handle(software)
    except TypeError:
        ('no communications software found for {}'.format(software))
        return None
    if window_handle is None:
        return
    # window_rect is (left, top, right, bottom) with top left as origin
    window_rect = win32gui.GetWindowRect(window_handle)
    # grab top fraction of image to reduce processing time
    window_top = (window_rect[0], window_rect[1], window_rect[2], window_rect[1] + \
                int((window_rect[3]-window_rect[1])*fraction))
    return window_top


def num_new_black_pixels(window_top):
    ''' Check software for a change. '''
    try:
        img = ImageGrab.grab(window_top)
    except OSError as e:
        logging.info('OSError: {}'.format(e))
        return None
    try:
        new_black = count_black_pixels(img)
        logging.debug('{} new_black: {}'.format(get_time(), new_black))
    except ZeroDivisionError as e:
        logging.info('ZeroDivisionError: {}'.format(e))
        return None
    if new_black:
        return new_black
    else:
        return None


def check_limit(new_black, old_black, limit):
    ''' Have we exceeded the threshold for new black pixels? '''
    logging.debug('new_black: {}, old_black: {}, limit: {}'.format(new_black, old_black, limit))
    if abs(new_black - old_black) > limit:
        logging.info('Change detected')
        return True
    return False


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
        logging.info('*** looking for a microbit')
        mbit_port = get_comport(PID_MICROBIT, VID_MICROBIT, BAUD)
        logging.info('microbit found at comport: {}'.format(mbit_port))
        with Serial_Con(mbit_port) as mbit_serial:
            # occasionally mbit_serial is not created, so is None
            if not mbit_serial:
                logging.info('failed to create mbit_serial')
                time.sleep(0.5)
                continue
            logging.info('microbit serial port created at: {}'.format(mbit_port))
            mbit_serial.write(b'flash')
            while True:
                time.sleep(0.5)
                # look for the top fraction of a window running the target software
                window_top = get_window_top(fraction)
                if window_top is None:
                    continue
                # count black pixels in top fraction of target window
                new_black = num_new_black_pixels(window_top)
                logging.debug('new_black: {}'.format(new_black))
                if new_black is None:
                    continue
                is_limit_exceeded = check_limit(new_black, old_black, limit)
                if is_limit_exceeded:
                    try:
                        mbit_serial.write(b'flash')
                    except serial.SerialException as e:
                        logging.info('connection to microbit failed {}'.format(e))
                        break
                old_black = new_black


if __name__ == '__main__':
    main()
