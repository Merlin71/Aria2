## @file
## @brief AudioSubsystem plugin
import ConfigParser
import logging
import subprocess
import threading
import shlex
from time import sleep
from pydispatch import dispatcher

## @class Audio
## @brief AudioSubSystem plugin
## @details Allow sound playing and recording


class AudioSubSystem:
    version = "1.0.0.0"
    description = "Audio sub-system"

    ## @brief Create Audio subsystem instance
    ## @details Create Audio subsystem instance
    def __init__(self):
        self._hot_word_detection_active = threading.Event()
        self._io_system_busy = threading.Event()
        self._exit_flag = threading.Event()
        # Load logger
        try:
            self._logger = logging.getLogger('Audio')
        except ConfigParser.NoSectionError as e:
            print 'Fatal error  - fail to set logger.Error: %s ' % e.message
            raise ImportError
        self._logger.debug('Audio sub-system logger started')
        # Reading config file
        try:
            self._config = ConfigParser.SafeConfigParser(allow_no_value=True)
            self._config.read('./configuration/audio.conf')
        except ConfigParser.Error as e:
            self._logger.error('Fail to read configuration file with error %s.Module unload' % e)
            raise ImportError
        try:
            self._hot_words = self._config.get('Activation', 'hot_words').split(';')
            engine = self._config.get('Activation', 'engine')
            command_line = self._config.get('Activation', 'options')
            dictionary = self._config.get('Activation', 'dictionary')
            lang_model = self._config.get('Activation', 'lang_model')
            log_redirect = self._config.get('Activation', 'log_redirect')
            command_line = command_line.replace('$dict$', dictionary)
            command_line = command_line.replace('$lang$', lang_model)
            self._recognition_engine = shlex.split(engine + ' ' + command_line + ' ' + log_redirect)

            playback_engine = self._config.get('Playback', 'engine')
            playback_option = self._config.get('Playback', 'options')
            playback_log_redirect = self._config.get('Playback', 'log_redirect')
            self._playback_engine = shlex.split(playback_engine + ' ' + playback_option + ' ' + playback_log_redirect)

            record_engine = self._config.get('Record', 'engine')
            record_option = self._config.get('Record', 'options')
            record_log_redirect = self._config.get('Record', 'log_redirect')
            self._max_record_time = self._config.get('Record', 'max_record_time')

            self._record_engine = shlex.split(record_engine + ' ' + record_option + ' ' + record_log_redirect)

            if self._config.getboolean('Activation', 'auto_start'):
                self.start_hot_word_detection(10)
        except ConfigParser.Error as e:
            self._logger.error('Fail to read configuration file with error %s.Module unload' % e)
            raise ImportError
        # Register on Events
        try:
            dispatcher.connect(self.start_hot_word_detection, signal='WaitToHotWord', sender=dispatcher.Any)
        except dispatcher.DispatcherTypeError as e:
            self._logger.error('Fail to subscribe on "WaitToHotWord" event with error %s.Module unload' % e)
            raise ImportError

        try:
            dispatcher.connect(self.play_file, signal='PlayFile', sender=dispatcher.Any)
        except dispatcher.DispatcherTypeError as e:
            self._logger.error('Fail to subscribe on "PlayFile" event with error %s.Module unload' % e)
            raise ImportError

        try:
            dispatcher.connect(self.record_file, signal='RecordFile', sender=dispatcher.Any)
        except dispatcher.DispatcherTypeError as e:
            self._logger.error('Fail to subscribe on "RecordFile" event with error %s.Module unload' % e)
            raise ImportError

    def __del__(self):
        dispatcher.disconnect(self.start_hot_word_detection)
        dispatcher.disconnect(self.play_file)
        self._exit_flag.set()
        sleep(5)
        if self._hot_word_detection_active.isSet():
            self._logger.error('Fail to stop recognition process')
        if self._io_system_busy.isSet():
            self._logger.error('Fail to stop playback process')
        self._logger.debug('Audio module release')

    def start_hot_word_detection(self, delay=None):
        if self._exit_flag.is_set():
            self._logger.warning('Shutdown flag set. Ignoring start command')
            return
        self._logger.info('Starting Hot word detection')
        try:
            threading.Thread(target=self._start_hot_word_detection, args=(delay,)).start()
        except threading.ThreadError as e:
            self._logger.error('Fail top start detection thread with error %s' % e)

    def _start_hot_word_detection(self, delay=None):
        if delay is not None:
            sleep(delay)
        self._logger.info('Starting recognize process')
        dispatcher.send(signal='HotWordDetectionActive', status=True)
        _recognize_process = subprocess.Popen(self._recognition_engine, stdout=subprocess.PIPE)
        self._hot_word_detection_active.set()
        while not self._exit_flag.isSet():
            line = _recognize_process.stdout.readline().replace('\n', ' ').replace('\r', '')
            if self._io_system_busy.isSet():
                self._logger.info('Playback started.Stop recognition process')
                dispatcher.send(signal='HotWordDetectionActive', status=False)
                _recognize_process.terminate()
                self._hot_word_detection_active.clear()
                while self._io_system_busy.isSet():
                    sleep(1)
                dispatcher.send(signal='HotWordDetectionActive', status=True)
                _recognize_process = subprocess.Popen(self._recognition_engine, stdout=subprocess.PIPE)
                self._hot_word_detection_active.set()
            if line != '':
                for word in self._hot_words:
                    if word in line:
                        self._logger.info('Hot word %s detected in input %s' % (word, line))
                        self._logger.info('Stop recognition process')
                        dispatcher.send(signal='HotWordDetected', text=word)
                        dispatcher.send(signal='HotWordDetectionActive', status=False)
                        self._hot_word_detection_active.clear()
                        _recognize_process.terminate()
                        return

    def play_file(self, filename, delay=None, callback=None):
        if self._exit_flag.is_set():
            self._logger.warning('Shutdown flag set. Ignoring start command')
            return
        self._logger.info('Starting file playback')
        try:
            threading.Thread(target=self._play_file, args=(filename, delay, callback)).start()
        except threading.ThreadError as e:
            self._logger.error('Fail to start playback thread with error %s' % e)

    def _play_file(self, filename, delay=None, callback=None):
        if delay is not None:
            sleep(delay)
        if self._io_system_busy.isSet():
            self._logger.warning('Another playback active waiting to end')
        while self._io_system_busy.isSet():
            sleep(1)
        self._io_system_busy.set()
        if self._hot_word_detection_active.isSet():
            self._logger.warning('Hot word detection running waiting to termination')
        while self._hot_word_detection_active.isSet():
            sleep(1)
        try:
            dispatcher.send(signal='PlaybackActive', status=True)
            subprocess.call([s.replace('$file$', filename) for s in self._playback_engine])
        except OSError as e:
            self._logger.error('Fail to play file %s with error %s' % (filename, e))
        finally:
            dispatcher.send(signal='PlaybackActive', status=False)
            self._io_system_busy.clear()
            
        if callable(callback):
            callback()

    def record_file(self, filename, record_time=None, delay=None, callback=None):
        if self._exit_flag.is_set():
            self._logger.warning('Shutdown flag set. Ignoring start command')
            return
        if record_time is None:
            record_time = self._max_record_time
        elif record_time > self._max_record_time:
            self._logger.warning('Record time too large reducing')
        self._logger.info('Starting audio record')
        try:
            threading.Thread(target=self._record_file, args=(filename, record_time, delay, callback)).start()
        except threading.ThreadError as e:
            self._logger.error('Fail to start audio record thread with error %s' % e)

    def _record_file(self, filename, record_time, delay=None, callback=None):
        if delay is not None:
            sleep(delay)
        if self._io_system_busy.isSet():
            self._logger.warning('Another playback active waiting to end')
        while self._io_system_busy.isSet():
            sleep(1)
        self._io_system_busy.set()
        if self._hot_word_detection_active.isSet():
            self._logger.warning('Hot word detection running waiting to termination')
        while self._hot_word_detection_active.isSet():
            sleep(1)

        try:
            call_command = [s.replace('$file$', filename) for s in self._record_engine]
            call_command = [s.replace('$time$', record_time) for s in call_command]
            dispatcher.send(signal='RecordActive', status=True)
            subprocess.call(call_command)
        except OSError as e:
            self._logger.error('Fail to record file %s with error %s' % (filename, e))
        finally:
            self._io_system_busy.clear()
            dispatcher.send(signal='RecordActive', status=False)

        if callable(callback):
            callback(filename)
