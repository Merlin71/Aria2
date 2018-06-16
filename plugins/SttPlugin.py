## @file
## @brief Speech-To-Text
## @details Contain function interact with WIT.AI servers.
##  Allow Speech-to-Tesx conversion adn Natural-Language-Processing
## par Configuration file
## @verbinclude ./configuration/stt.conf
#
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
## @version 1.0.0.2
class STT:
    ## @brief Plugin version
    version = '1.0.0.2'
    ## @brief Short plugin description
    description = 'Interface to WIT STT engine'

    ## @brief STT and NLP abstraction
    ## @details Create and initialize instance for WIT.ai STT and NLP engine
    ## @exception ImportError Configuration or IO system error - Module will be unloaded.
    ## @par Registering on events:
    # HotWordDetected - Wait until Hot-Word not detected in audio input and send notification.\n
    # SpeechAccepted - Wait until module recognize text and start processing
    # SayResponse - System response.\n
    # VoiceActivationAccepted - True if Hot-Word detect.\n
    #
    ## @par Generate events:
    # GuiNotification - GUI tray update.\n
    #
    ## @see guiPlugin
    ## @see AudioSubSystem
    def __init__(self):
        ## @brief Notify flag to restart Hot-Word detection if no module start processing
        self._processing_accepted = threading.Event()
        ## @brief Unique id for GUI tray notification
        self._gui_recognize_uuid = str(uuid4())
        # Load logger
        try:
            ## @brief Logger instance
            self._logger = logging.getLogger('moduleSTT')
        except ConfigParser.NoSectionError as e:
            print 'Fatal error  - fail to set logger.Error: %s ' % e.message
            raise ImportError
        self._logger.debug('STT logger started')
        # Reading config file
        try:
            ## @brief Configuration instance
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
            ## @brief Activation Hot-Word list
            self.activation = self._config.get('Reaction', 'activation_phrase')
            self.activation = self.activation.split(';')
            self._logger.debug('Activation phrase: %s' % self.activation)
            ## @brief Path to  temporary folder
            self._temp_folder = self._config.get('Folders', 'TempFolder')
            if not os.path.exists(self._temp_folder):
                os.makedirs(self._temp_folder)
        except ConfigParser.Error as e:
            self._logger.error('Fail to read configuration file with error %s.Module unload' % e)
            raise ImportError

        ## @brief WIT.AI communication instance
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

    ## @brief Stop module
    ## @details Empty module - required only for compatibility
    def __del__(self):
        pass

    # @brief HotWordDetected event wrapper
    ## @details Start user voice recording
    ## @warning This function should not be called from outside
    ## @par Generate events:
    # GuiNotification - GUI tray update.\n
    # VoiceActivationAccepted - Set to True if Hot-Word accepted by module
    #
    ## @param text Detected text by local STT engine
    ## @see guiPlugin
    ## @see TTS
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

    ## @brief Callback function
    ## @details Start thread to communicate with WIT.AI servers
    ## @param filename Path to wave file with user voice request
    def wav_analyze(self, filename):
        threading.Thread(target=self._wav_analyze, args=(filename,)).start()

    ## @brief Convert wave file into text
    ## @details Send file to WIT.AI servers and, receive raw text, and text entities
    ## @param filename path to wave file that be send to WIT.AI server
    ## @todo Remove silence
    def _wav_analyze(self, filename):
        self._logger.debug('File record complete - filename %s' % filename)
        dispatcher.send(signal='SayResponse', response='Processing')
        dispatcher.send(signal='GuiNotification', source=self._gui_recognize_uuid, icon_path="analyzing.png")
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
            dispatcher.send(signal='GuiNotification', source=self._gui_recognize_uuid, icon_path="")

    ## @brief Restart user interaction
    ## @details After request process restart hot-word detection process
    ## @warning This function should not be called from outside
    ## @par Generate events:
    # RestartInteraction - restart Hot-Word detection.\n
    #
    ## @see SttPlugin
    def restart_interaction(self):
        self._logger.debug('Restarting hot word detection')
        dispatcher.send(signal='WaitToHotWord')

    ## @brief Notify start data process
    ## @details Notifu to other thread about data processeing
    ## @warning This function should not be called from outside
    def speech_data_accepted(self):
        self._processing_accepted.set()
