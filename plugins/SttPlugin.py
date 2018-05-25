## @file
## @brief STT plugin
import ConfigParser
import logging
import subprocess
import os
from pydispatch import dispatcher
import keyring
import uuid
import json
import threading
from time import sleep
from uuid import uuid4

from wit import Wit

## @class STT
## @brief Speech to Text abstraction
## @details Allow interface with STT engine
class STT:
    version = '1.0.0.2'
    description = 'Interface to WIT STT engine'

    ## @brief Create STT instance
    ## @details Create STT instance
    def __init__(self):
        self._processing_accepted = threading.Event()
        self.gui_recognize_uuid = str(uuid4())
        # Load logger
        try:
            self._logger = logging.getLogger('moduleSTT')
        except ConfigParser.NoSectionError as e:
            print 'Fatal error  - fail to set logger.Error: %s ' % e.message
            raise ImportError
        self._logger.debug('STT logger started')
        # Reading config file
        try:
            self._config = ConfigParser.SafeConfigParser(allow_no_value=False)
            self._config.read('./configuration/stt.conf')
            api_system = self._config.get('API', 'system')
            api_user = self._config.get('API', 'user')
            try:
                api_key = keyring.get_password(api_system, api_user)
            except keyring.errors as e:
                self._logger.warning('Fail to read WIT.AI token with error: %s. Refer to manual. Module unload' % e)
                raise ImportError
            if api_key is None:
                self._logger.warning('Fail to read WIT.AI token. Refer to manual. Module unload')
                raise ImportError
            self.activation = self._config.get('Reaction', 'activation_phrase')
            self.activation = self.activation.split(';')
            self._logger.debug('Activation phrase: %s' % self.activation)
            self._temp_folder = self._config.get('Folders', 'TempFolder')
            if not os.path.exists(self._temp_folder):
                os.makedirs(self._temp_folder)
        except ConfigParser.Error as e:
            self._logger.error('Fail to read configuration file with error %s.Module unload' % e)
            raise ImportError

        self.client = Wit(api_key)
        try:
            dispatcher.connect(self.record_user, signal='HotWordDetected', sender=dispatcher.Any)
        except dispatcher.DispatcherTypeError as e:
            self._logger.error('Fail to subscribe on "HotWordDetected" event with error %s.Module unload' % e)
            raise ImportError
        try:
            dispatcher.connect(self.restart_interaction, signal='RestartInteraction', sender=dispatcher.Any)
        except dispatcher.DispatcherTypeError as e:
            self._logger.error('Fail to subscribe on "RestartInteraction" event with error %s.Module unload' % e)
            raise ImportError
        try:
            dispatcher.connect(self.speech_data_accepted, signal='SpeechAccepted', sender=dispatcher.Any)
        except dispatcher.DispatcherTypeError as e:
            self._logger.error('Fail to subscribe on "RestartInteraction" event with error %s.Module unload' % e)
            raise ImportError

    def __del__(self):
        pass

    def record_user(self, text):
        for test_phrase in self.activation:
            if text in test_phrase:
                self._logger.info('Detected activation phrase %s in text input %s' % (test_phrase, self.activation))
                break
        else:
            self._logger.debug('Activation phrase not found. Ignoring..')
            dispatcher.send(signal='RestartInteraction')
            return
        dispatcher.send(signal='SayResponse', response='Activation')
        dispatcher.send(signal='VoiceActivationAccepted', status=True, sender='STT')  # Special message for brain module
        record_filename = os.path.join(self._temp_folder, str(uuid.uuid4()) + '.wav')
        self._logger.debug('Requesting record into %s' % record_filename)
        dispatcher.send(signal='RecordFile', filename=record_filename, callback=self.wav_analyze)

    def wav_analyze(self, filename):
        threading.Thread(target=self._wav_analyze, args=(filename,)).start()

    def _wav_analyze(self, filename):
        self._logger.debug('File record complete - filename %s' % filename)
        dispatcher.send(signal='SayResponse', response='Processing')
        dispatcher.send(signal='GuiNotification', source=self.gui_recognize_uuid, icon_path="analyzing.png")
        # TODO - Remove silence
        try:
            resp = None
            self._logger.debug('Connection to speech processing engine')
            with open(filename, 'rb') as f:
                resp = self.client.speech(f, None, {'Content-Type': 'audio/wav'})
                with open(filename[:-3] + 'json', 'w') as fp:
                    json.dump(resp, fp)
        except:
            self._logger.warning('Fail to analyze speech with error')
            dispatcher.send(signal='SayResponse', response='Unclear')
            dispatcher.send(signal='RestartInteraction')
        else:
            self._logger.debug('Recognized speech %s ' % resp)
            self._logger.debug('Got entities %s ' % resp['entities'])
            self._processing_accepted.clear()
            dispatcher.send(signal='SpeechRecognize', entities=resp['entities'], raw_text=resp['_text'])
            # Wait to end of processing
            sleep(5)
            test = self._processing_accepted.wait(timeout=10)
            print test
            if test:
                self._logger.debug("Response received")
            else:
                self._logger.warning('No response from any module')
                dispatcher.send(signal='SayResponse', response='Unclear')
                sleep(5)
                dispatcher.send(signal='RestartInteraction')
        finally:
            dispatcher.send(signal='GuiNotification', source=self.gui_recognize_uuid, icon_path="")

    def restart_interaction(self):
        self._logger.debug('Restarting hot word detection')
        dispatcher.send(signal='WaitToHotWord')

    def speech_data_accepted(self):
        self._processing_accepted.set()
