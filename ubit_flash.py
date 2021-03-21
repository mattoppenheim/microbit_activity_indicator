''' show animation when signal received over serial port
This file  should be written to the BBC Micro:bit using Mu
matt.oppenheim@gmail.com '''
from microbit import *

# baud rate for the serial port connection
BAUD = 9600

throb_1 = Image(
    '00100:'
    '00100:'
    '00100:'
    '00000:'
    '00000:')

throb_2 = Image(
    '10000:'
    '01000:'
    '00100:'
    '00000:'
    '00000:')

throb_3 = Image(
    '00000:'
    '00000:'
    '11100:'
    '00000:'
    '00000:')

throb_4 = Image(
    '00000:'
    '00000:'
    '00100:'
    '01000:'
    '10000:')

throb_5 = Image(
    '00000:'
    '00000:'
    '00100:'
    '00100:'
    '00100:')

throb_6 = Image(
    '00000:'
    '00000:'
    '00100:'
    '00010:'
    '00001:')

throb_7 = Image(
    '00000:'
    '00000:'
    '00111:'
    '00000:'
    '00000:')

throb_8 = Image(
    '00001:'
    '00010:'
    '00100:'
    '00000:'
    '00000:')

throbs = [throb_1, throb_2, throb_3, throb_4, throb_5, throb_6,
          throb_7, throb_8]


def check_uart():
    ''' returns true if control character received '''
    in_line = None
    try:
        in_line = uart.readline()
    except Exception as e:
        print(e)
    if not in_line:
        return False
    if in_line == b"flash":
            return True


def show_ready():
    display.show(throb_1*9)


def show_throb():
    for a in range(len(throbs)):
        display.show(throbs[a]*9 +
                     throbs[a-1]*6 +
                     throbs[a-2]*4)
        sleep(100)


uart.init(baudrate=BAUD)

while True:
    if check_uart():
        show_throb()
    if button_a.is_pressed():
        show_throb()
    else:
        show_ready()
    sleep(100)
