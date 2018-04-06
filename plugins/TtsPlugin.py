## @file
## @brief TTS plugin
import ConfigParser
import logging
import subprocess
import threading
import os
import hashlib
from pydispatch import dispatcher


## @class TTS
## @brief Test To Speech abstraction
## @details Allow interface with TTS engine
## @par Interact with TTS engine need generate 'Speak' event in pubsub system
##
## @code{.py}
## from pubsub import pub
## tts_engine = TTS(config)
## #some work
## pub.sendMessage('SpeakText', text2say="Hello")
## @endcode
class TTS:
    version = '1.0.0.1'
    description = 'Python wrapper for TTS - festeval'

    ## @brief Create TTS instance
    ## @details Create TTS instance
    def __init__(self):
        # Load logger
        try:
            self._logger = logging.getLogger('moduleTTS')
        except ConfigParser.NoSectionError as e:
            print 'Fatal error  - fail to set logger.Error: %s ' % e.message
            raise ConfigParser.NoSectionError
        self._logger.debug('TTS logger started')
        # Reading config file
        try:
            self._config = ConfigParser.SafeConfigParser(allow_no_value=True)
            self._config.read('./configuration/tts.conf')
        except ConfigParser.Error as e:
            self._logger.error('Fail to read configuration file with error %s.Module unload' % e)
            return
        # Creating temp folder
        self._cache_folder = self._config.get('Folders', 'TempFolder')
        if not os.path.exists(self._cache_folder):
            try:
                os.makedirs(self._cache_folder)
            except IOError as e:
                self._logger.error('Fail to temporary folder with error %s.Module unload' % e)
                return
        try:
            self.tts_command = self._config.get('TTS', 'command')
        except ConfigParser.Error as e:
            self._logger.error('Fail to load tts configuration with error %s.Module unload' % e)
            return
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
            return
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
        pass

    ## @brief Send text into text2wav instance
    ## @param[in] text Text to say
    def text2wav(self, sender, text):
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

        subprocess.call(['aplay', wave_file])

    def _synthesize(self,text_file, wave_file, text):
        # Write new text file
        try:
            f = open(text_file, 'w')
            f.write(text)
            f.close()
        except IOError as e:
            self._logger.error('Fail create speech file.Error : %s' % e)
        # Synthesize new wave file
        try:
            subprocess.call(['text2wave', str(text_file), '-o', str(wave_file)])
        except OSError as e:
            self._logger.error('Fail to communicate with TTS engine.Error : %s' % e)

