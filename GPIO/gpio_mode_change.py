import logging
import RPi.GPIO as GPIO
import subprocess
import pwnagotchi.plugins as plugins
import os


#config lines
#main.plugins.gpio_mode_change.enabled = true
#main.plugins.gpio_mode_change.gpio_port = 6


class GPIOChangeMode(plugins.Plugin):
    __author__ = 'havivv1305@gmail.com'
    __version__ = '1.0.0'
    __license__ = 'GPL3'
    __description__ = 'GPIO Button change mode'

    def __init__(self):
        self.ready = False

    def restart_to_auto(self):
        logging.info("restarting in AUTO mode ...")
        os.system("touch /root/.pwnagotchi-auto")

    def restart_to_man(self):
        logging.info("restarting in MANO mode ...")
        os.system("touch /root/.pwnagotchi-manual")

    def man_mode_active(self):
        process = subprocess.Popen('service pwnagotchi status', shell=True,stdout=subprocess.PIPE,stderr=None,stdin=None,executable="/bin/bash")
        out,_ = process.communicate()
        if '--manual' in str(out):
            return 'AUTO'
        else:
            return 'MANO'
        
    def restart_mode(self,a):
        stat = self.man_mode_active()
        if stat == 'AUTO':
            self.restart_to_auto()
        else:
            self.restart_to_man()
        
        os.system("service bettercap restart")
        os.system("service pwnagotchi restart")

    def on_loaded(self):
        logging.info("GPIO Button change mode plugin loaded.")
        try:
            # get GPIO
            gpio_port = self.options['gpio_port']

            # set gpio numbering
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(gpio_port, GPIO.IN, GPIO.PUD_UP)
            GPIO.add_event_detect(gpio_port, GPIO.FALLING, callback=self.restart_mode, bouncetime=600)
        except Exception as e:
            logging.error(e)
            logging.error(f'GPIO port: {gpio_port}')

