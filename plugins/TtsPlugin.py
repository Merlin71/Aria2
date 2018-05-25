## @file
## @brief TTS plugin
import ConfigParser
import logging
import subprocess
import os
import hashlib
from time import time
from pydispatch import dispatcher
import random
from uuid import uuid4

## @class TTS
## @brief Test To Speech abstraction
## @details Allow interface with TTS engine
## @par Interact with TTS engine need generate 'SayText' event in dispatcher system
##
## @code{.py}
## from pydispatch import dispatcher
## tts_engine = TTS()
## #some work
## dispatcher.send(signal='SayText', text='Hello')
## @endcode
class TTS:
    version = '1.0.0.1'
    description = 'Python wrapper for TTS - festeval'

    ## @brief Create TTS instance
    ## @details Create TTS instance
    def __init__(self):
        self.gui_synthesis_status_uuid = str(uuid4())
        # Load logger
        try:
            self._logger = logging.getLogger('moduleTTS')
        except ConfigParser.NoSectionError as e:
            print 'Fatal error  - fail to set logger.Error: %s ' % e.message
            raise ImportError
        self._logger.debug('TTS logger started')
        # Reading config file
        try:
            self._config = ConfigParser.SafeConfigParser(allow_no_value=False)
            self._config.read('./configuration/tts.conf')
        except ConfigParser.Error as e:
            self._logger.error('Fail to read configuration file with error %s.Module unload' % e)
            raise ImportError
        # Creating temp folder
        self._cache_folder = self._config.get('Folders', 'TempFolder')
        if not os.path.exists(self._cache_folder):
            try:
                os.makedirs(self._cache_folder)
            except IOError as e:
                self._logger.error('Fail to temporary folder with error %s.Module unload' % e)
                raise ImportError
        try:
            self.tts_command = self._config.get('TTS', 'command')
        except ConfigParser.Error as e:
            self._logger.error('Fail to load tts configuration with error %s.Module unload' % e)
            raise ImportError
        # Cache
        self._cached_text = list()
        try:
            self._use_cache = self._config.getboolean('Cache', 'Allow')
            self._cache_size = self._config.getint('Cache', 'MaxItems')
            self._clear_on_exit = self._config.getboolean('Cache', 'ClearOnExit')
        except ConfigParser.Error as e:
            self._logger.error('Fail read cache settings with error %s. Using default.' % e)
            self._use_cache = True
            self._cache_size = 10
            self._clear_on_exit = True
        # Register for incoming events
        try:
            dispatcher.connect(self.text2wav, signal='SayText', sender=dispatcher.Any)
        except dispatcher.DispatcherTypeError as e:
            self._logger.error('Fail to subscribe on "SayText" event with error %s.Module unload' % e)
            raise ImportError
        try:
            dispatcher.connect(self.response, signal='SayResponse', sender=dispatcher.Any)
        except dispatcher.DispatcherTypeError as e:
            self._logger.error('Fail to subscribe on "SayResponse" event with error %s.Module unload' % e)
            raise ImportError
        self._logger.info('TTS module ready')

    ## @brief Stop  tts engine and delete tts instance
    def __del__(self):
        if self._clear_on_exit and self._use_cache:
            self._logger.debug('Removing cache')
            for cache_file in self._cached_text:
                #  Remove old items if any
                try:
                    self._logger.debug('Removing %s.wav' % cache_file)
                    os.remove(os.path.join(self._cache_folder, cache_file + '.wav'))
                except OSError as e:
                    self._logger.warning('Fail to remove old cached item with error %s' % e)

                try:
                    self._logger.debug('Removing %s.txt' % cache_file)
                    os.remove(os.path.join(self._cache_folder, cache_file + '.txt'))
                except OSError as e:
                    self._logger.warning('Fail to remove old cached item with error %s' % e)

        self._logger.debug('TTS module released')

    ## @brief Send text into text2wav instance
    ## @param[in] text Text to say
    def text2wav(self, sender, text, callback=None):
        self._logger.debug('Received text "%s" from module:%s' % (text, sender))
        text_hash = hashlib.sha1(text).hexdigest()
        wave_file = os.path.join(self._cache_folder, text_hash + '.wav')
        text_file = os.path.join(self._cache_folder, text_hash + '.txt')

        if self._use_cache:
            if os.path.isfile(wave_file):
                self._logger.debug('Cached text found')
                # Item will be re inserted at end
                try:
                    self._cached_text.remove(text_hash)
                except ValueError:
                    self._logger.info('Unlisted cache file found')
            else:
                self._logger.debug('Cache miss')
                while len(self._cached_text) > self._cache_size:
                    #  Remove old items if any
                    try:
                        self._logger.debug('Removing old item %s' % self._cached_text[0])
                        os.remove(os.path.join(self._cache_folder, self._cached_text[0] + '.wav'))
                        os.remove(os.path.join(self._cache_folder, self._cached_text[0] + '.txt'))
                    except IOError as e:
                        self._logger.warning('Fail to remove old cached item with error %s' % e)
                    self._cached_text = self._cached_text[1:]
                self._synthesize(text_file, wave_file, text)

            self._cached_text.append(text_hash)
        else:
            self._synthesize(text_hash, wave_file, text)

        dispatcher.send(signal='PlayFile', filename=wave_file, callback=callback)

    def _synthesize(self, text_file, wave_file, text):
        dispatcher.send(signal='SpeechSynthesize', status=True)
        dispatcher.send(signal='GuiNotification', source=self.gui_synthesis_status_uuid, icon_path="synthesis.png")
        self._logger.debug('Synthesize text "%s" using text file %s into wave file %s' %
                           (text, text_file, wave_file))
        # Write new text file
        try:
            f = open(text_file, 'w')
            f.write(text)
            f.close()
        except IOError as e:
            self._logger.error('Fail create speech file.Error : %s' % e)
            dispatcher.send(signal='SpeechSynthesize', status=False)
        # Synthesize new wave file
        try:
            self._logger.debug('Start voice synthesis')
            start_time = time()
            subprocess.call(['text2wave', str(text_file), '-o', str(wave_file)])
            self._logger.debug('Voice synthesis complete. Synthesis time %s sec' % (time() - start_time))
        except OSError as e:
            self._logger.error('Fail to communicate with TTS engine.Error : %s' % e)
        finally:
            dispatcher.send(signal='SpeechSynthesize', status=False)
            dispatcher.send(signal='GuiNotification', source=self.gui_synthesis_status_uuid, icon_path="")

    def response(self, response):
        try:
            response = self._config.get('Response', response)
        except ConfigParser as e:
            self._logger.warning('Fail to retrieve response %s with error %s' % (response, e))
        
        dispatcher.send(signal='SayText', text=random.choice(response.split(';')))

