## @file
## @brief Joke package
## @details Allow to system generate fun response
## par Configuration file
## @verbinclude ./configuration/humour.json
#
import ConfigParser
import logging
import json
from pydispatch import dispatcher
import random
import os
import threading


## @class Humor
## @brief Fun response module
## @details Make everyone smile
## @version 1.0.0.0
class Humour:
    ## @brief Plugin version
    version = '1.0.0.0'
    ## @brief Short plugin description
    description = 'Humour sense'

    ## @brief Initialize humor
    ## @details Initialize humor sense. Everyone should have one
    ## @exception ImportError Configuration or IO system error - Module will be unloaded. Not funny
    ## @par Registering on events:
    # SpeechRecognize - User to system text.
    #
    ## @par Generate events:
    # SpeechAccepted - Notify that module start process user request.\n
    # RestartInteraction - Restart Hot-Word detection.\n
    # SayText - Response to user request using TTS engine.\n
    # PlayFile - Response with audio file
    #
    ## @see AudioSubSystem
    ## @see TtsPlugin
    ## @see SttPlugin
    def __init__(self):
        # Load logger
        try:
            self._logger = logging.getLogger('moduleJoke')
        except ConfigParser.NoSectionError as e:
            print 'Fatal error  - fail to set logger.Error: %s ' % e.message
            raise ImportError
        self._logger.debug('Joke logger started - Lets fun begins')
        try:
            with open('./configuration/humour.json', 'r') as fp:
                self.humour=json.load(fp)
        except IOError as e:
            self._logger.warning('Fail to load humour database with error %s' % e)

        try:
            dispatcher.connect(self.joke, signal='SpeechRecognize', sender=dispatcher.Any)
        except dispatcher.DispatcherTypeError as e:
            self._logger.error('Fail to subscribe on "SpeechRecognize" event with error %s.Module unload' % e)
            raise ImportError

    ## @brief Wrapper for SpeechRecognize event
    ## @details Start thread to analyze user input text
    ## @param entities - Ignored
    ## @param raw_text - Text from STT engine
    def joke(self, entities, raw_text):
        threading.Thread(target=self._joke, args=(entities, raw_text)).start()

    ## @brief Response with joke
    ## @details Search for text in humor file and if found response with text\audio file
    ## @param entities - Ignored
    ## @param raw_text - Text from STT engine
    #
    ## @par Generate events:
    # SpeechAccepted - Notify that module start process user request.\n
    # RestartInteraction - Restart Hot-Word detection.\n
    # SayText - Response to user request using TTS engine.\n
    # PlayFile - Response with audio file
    #
    ## @see AudioPlugin
    ## @see TtsPlugin
    ## @see SttPlugin
    def _joke(self, entities, raw_text):
        if str(raw_text).lower() in self.humour:
            dispatcher.send(signal='SpeechAccepted')
            response_type = self.humour[str(raw_text).lower()]['type']
            if response_type == 'text':
                response_text = self.humour[str(raw_text).lower()]['text']
                dispatcher.send(signal='SayText', text=random.choice(response_text), callback=self.joke_done)
            elif response_type == 'sound':
                response_sound = self.humour[str(raw_text).lower()]['sound']
                response_sound = random.choice(response_sound)
                response_sound = os.path.join('./plugins/wav_data', response_sound)
                dispatcher.send(signal='PlayFile', filename=response_sound, callback=self.joke_done)

    ## @brief Restart user interaction
    ## @details After request process restart hot-word detection process
    ## @warning This function should not be called from outside
    ## @par Generate events:
    # RestartInteraction - restart Hot-Word detection.\n
    #
    ## @see SttPlugin
    @staticmethod
    def joke_done():
        dispatcher.send(signal='RestartInteraction')

