## @file
## @brief SPY plugin
import ConfigParser
import logging
from pydispatch import dispatcher
import os
import threading
from uuid import uuid4
import json
import subprocess
import re
import time

## @class Spy
## @brief Find MAC address in network
## @details Scan network and map MAC address
class Spy:
    version = '1.0.0.0'
    description = 'Network scanner'

    def __init__(self):
        self._gui_status = str(uuid4())
        self._shutdown = threading.Event()
        self._detected_user = dict()
        self._update_lock = threading.Lock()

        try:
            self._logger = logging.getLogger('moduleSpy')
        except ConfigParser.NoSectionError as e:
            print 'Fatal error  - fail to set logger.Error: %s ' % e.message
            raise ImportError
        self._logger.debug('Network scanner logger started')
        # Reading config file
        try:
            self._config = ConfigParser.SafeConfigParser(allow_no_value=False)
            self._config.read('./configuration/net_scan.conf')
            self._temp_folder = self._config.get('General', 'temp_folder')
            self._network = self._config.get('General', 'network')
            self.scan_time = self._config.getfloat('General', 'scan_time')
        except ConfigParser.Error as e:
            self._logger.error('Fail to read configuration file with error %s.Module unload' % e)
            raise ImportError

        try:
            with open("./configuration/net_map.json", "r") as data_file:
                self.user_map = json.load(data_file)
        except (IOError, ValueError) as e:
            self._logger.error('Fail to read data file with error %s.Module unload' % e)
            raise ImportError

        if not os.path.exists(self._temp_folder):
            try:
                os.makedirs(self._temp_folder)
            except IOError as e:
                self._logger.error('Fail to temporary folder with error %s.Module unload' % e)
                raise ImportError

        try:
            # register on user input
            dispatcher.connect(self.active_user, signal='GetActiveUser', sender=dispatcher.Any)
        except dispatcher.DispatcherTypeError as e:
            self._logger.error('Fail to subscribe on events with error %s.Module unload' % e)
            raise ImportError
        
        self._logger.info('Starting passive scan')
        threading.Thread(target=self._scan_network).start()

    def __del__(self):
        self._logger.info('Shutdown')
        self._shutdown.set()

    def _scan_network(self):
        while not self._shutdown.isSet():
            self._shutdown.wait(self.scan_time)
            if self._shutdown.isSet():
                self._logger.info('Shutdown event - stop scan')
                return
            self._logger.debug('Starting scan')
            subprocess.Popen(["nmap", "-sn", self._network])

            self._logger.debug('Search for MACs')
            try:
                os.remove(os.path.join(self._temp_folder, "mac.txt"))
            except OSError:
                pass
            with open(os.path.join(self._temp_folder, "mac.txt"), "w") as file_:
                subprocess.Popen(["arp", "-v"], stdout=file_)
                file_.flush()

            time.sleep(5)
            with open(os.path.join(self._temp_folder, "mac.txt"), "r") as file_:
                for line_ in file_:
                    mac = re.search('([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})', line_)
                    if mac is not None:
                        if str(mac.group(0)) in self.user_map:
                            self._update_lock.acquire()
                            # Set last active status
                            self._detected_user[self.user_map[str(mac.group(0))]] = time.time()
                            self._update_lock.release()

    def active_user(self, callback, custom_obj):
        users = []
        self._update_lock.acquire()
        for user, last_time in self._detected_user.iteritems():
            if time.time() - last_time < (3 * self.scan_time):
                users.append(user)
        self._update_lock.release()
        callback(custom_obj, users)

