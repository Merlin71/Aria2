## @file
## @brief Joke plugin
import ConfigParser
import logging
import json
from pydispatch import dispatcher
import random
import os
import threading


## @class Joke
## @brief Fun response module
## @details Make everyone smile
class Humour:
    version = '1.0.0.0'
    description = 'Humour sense'

    ## @brief Create STT instance
    ## @details Create STT instance
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
            self._logger.error('Fail to subscribe on "HotWordDetected" event with error %s.Module unload' % e)
            raise ImportError

    def joke(self, entities, raw_text):
        threading.Thread(target=self._joke, args=(entities, raw_text)).start()

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

    def joke_done(self):
        dispatcher.send(signal='RestartInteraction')

