# Based on UPS Lite v1.3 from https://github.com/xenDE
#
# functions for get UPS status - needs enable "i2c" in raspi-config
# 
# https://github.com/linshuqin329/UPS-Lite
# config line:
#main.plugins.ups_lite_1_3.enabled = true

# To display external power supply status you need to bridge the necessary pins on the UPS-Lite board. See instructions in the UPS-Lite repo.
import logging
import struct
from time import sleep

import RPi.GPIO as GPIO

import pwnagotchi
import pwnagotchi.plugins as plugins
import pwnagotchi.ui.fonts as fonts
from pwnagotchi.ui.components import LabeledValue
from pwnagotchi.ui.view import BLACK

CW2015_ADDRESS   = 0X62
CW2015_REG_VCELL = 0X02
CW2015_REG_SOC   = 0X04
CW2015_REG_MODE  = 0X0A

Full_Battery = 98.0
Half_Battery = 50.0
Die_Battery = 15.0
Shutdown_On = 2.0
BT_Auto = False # Auto enable BT tethering when battery is above 50% and disable when below 50%

# TODO: add enable switch in config.yml an cleanup all to the best place
class UPS:
    def __init__(self):
        # only import when the module is loaded and enabled
        import smbus
        self._bus = smbus.SMBus(1)

    def voltage(self):
        try:
            "This function returns as float the voltage from the Raspi UPS Hat via the provided SMBus object"
            read = self._bus.read_word_data(CW2015_ADDRESS, CW2015_REG_VCELL)
            swapped = struct.unpack("<H", struct.pack(">H", read))[0]
            voltage = swapped * 0.305 /1000
            return voltage
        except Exception as e:
            logging.error('UPS V1.3: {e}'.format(e=e))
            return 'err'

    def capacity(self):
        try:
            "This function returns as a float the remaining capacity of the battery connected to the Raspi UPS Hat via the provided SMBus object"
            read = self._bus.read_word_data(CW2015_ADDRESS, CW2015_REG_SOC)
            swapped = struct.unpack("<H", struct.pack(">H", read))[0]
            capacity = swapped/256
            return capacity
        except Exception as e:
            logging.error('UPS V1.3: {e}'.format(e=e))
            return 'err'

    def charging(self):
        try:
            if (GPIO.input(4) == GPIO.HIGH):       
                return '+'
            if (GPIO.input(4) == GPIO.LOW):      
                return '-'
        except Exception as e:
            logging.error('UPS V1.3: {e}'.format(e=e))
            return 'err'


class UPSLite(plugins.Plugin):
    __author__ = 'evilsocket@gmail.com'
    __editedby__ = 'Kilg00re - Havivv1305@gmail.com'
    __version__ = '1.0.0'
    __license__ = 'GPL3'
    __description__ = 'A plugin that will add a voltage indicator for the UPS Lite v1.3'

    def __init__(self):
        self.ups = None
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(4,GPIO.IN)  # GPIO4 is used to detect whether an external power supply is inserted

    def on_loaded(self):
        logging.info('UPS V1.3: Successfully loaded ...')  
        self.ups = UPS()

    def on_ui_setup(self, ui):
        ui.add_element('ups', LabeledValue(color=BLACK, label='B', value='-%', position=(ui.width() / 2 + 15, 0),
                                           label_font=fonts.Bold, text_font=fonts.Medium))

    def on_unload(self, ui):
        logging.info('UPS V1.3: Successfully Unloaded ...')  
        with ui._lock:
            ui.remove_element('ups')

    def on_ui_update(self, ui):
        logging.debug('UPS V1.3: start checking')  
        capacity = self.ups.capacity()
        charging = self.ups.charging()
        logging.debug(f'UPS V1.3: battery on "{capacity}%" and charging is: "{charging}"')
        if type(capacity) == float:
            capacity = int(capacity)
            with ui._lock:
                ui.set('ups', f"{capacity}{charging}%")
                if capacity >= Full_Battery and charging == '+':
                    if BT_Auto:
                        plugins.toggle_plugin(name='bt-tether', enable=True)
                    logging.info(f'UPS V1.3: Full battery (>= {Full_Battery}%)')
                    #ui.update(force=True, new_data={'status': 'Battery full'})
                elif capacity > Half_Battery and charging == '-':
                    logging.info('UPS V1.3: battery is above 50%% enable tethering')
                    if BT_Auto:
                        plugins.toggle_plugin(name='bt-tether', enable=True)
                    #ui.update(force=True, new_data={'status': 'Battery full'})

                if capacity == 100:
                    logging.info('UPS V1.3: Full battery 100%')
                    if BT_Auto:
                        plugins.toggle_plugin(name='bt-tether', enable=True)
                    #ui.update(force=True, new_data={'status': 'Battery full'})
                elif capacity <= Half_Battery and  charging == '-':
                    logging.info(f'UPS V1.3: Half way battery (<= {Half_Battery}%) disable tethering')
                    if BT_Auto:
                        plugins.toggle_plugin(name='bt-tether', enable=False)
                    #ui.update(force=True, new_data={'status': 'Battery in half way'})
                elif capacity <= Die_Battery and  charging == '-':
                    if BT_Auto:
                        plugins.toggle_plugin(name='bt-tether', enable=False)
                    logging.info(f'UPS V1.3: Low battery (<= {Die_Battery}%) disable tethering')
                    #ui.update(force=True, new_data={'status': 'Battery about to die please charge!'})
                elif capacity <= Shutdown_On and  charging == '-':
                    logging.info(f'UPS V1.3: Empty battery (<= {Shutdown_On}%): shuting down')
                    #ui.update(force=True, new_data={'status': 'Battery exhausted, bye ...'})
                    pwnagotchi.shutdown()
        else:
            with ui._lock:
                ui.set('ups', f"ERR")
                logging.info('UPS V1.3: No battery detected')
                #ui.update(force=True, new_data={'status': 'No battery detected'})
        
