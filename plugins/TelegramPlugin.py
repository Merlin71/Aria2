## @file
## @brief Telegram Bot plugin

import ConfigParser
import logging
import threading
import time
import dateutil.parser
from uuid import uuid4

import telegram.ext
import telegram

import picamera

import keyring
from pydispatch import dispatcher


class TelegramBot:
    version = '1.0.0.0'
    description = 'Telegram bot'

    def __init__(self):
        self.gui_status = str(uuid4())
        self._shutdown = threading.Event()
        self.response = TelegramCommandHandlers()

        try:
            self._logger = logging.getLogger('moduleTelegram')
        except ConfigParser.NoSectionError as e:
            print 'Fatal error  - fail to set logger.Error: %s ' % e.message
            raise ImportError
        self._logger.debug('Telegram bot logger started')
        # Reading config file
        try:
            self._config = ConfigParser.SafeConfigParser(allow_no_value=False)
            self._config.read('./configuration/telegram.conf')
            api_system = self._config.get('API', 'system')
            self.api_user = self._config.get('API', 'user')
        except ConfigParser.Error as e:
            self._logger.error('Fail to read configuration file with error %s.Module unload' % e)
            raise ImportError

        try:
            self.api_key = keyring.get_password(api_system, self.api_user)
        except keyring.errors as e:
            self._logger.warning('Fail to read Telegram access token with error: %s. Refer to manual. Module unload' % e)
            raise ImportError

        if self.api_key is None:
            self._logger.warning('Fail to read Telegram access token. Refer to manual. Module unload')
            raise ImportError

        self._logger.info('Starting new Bot service')
        try:
            self._bot_update = telegram.ext.Updater(self.api_key)
            # Shut up annoying logger
            self._bot_update.logger.setLevel(logging.INFO)
            _annoying_logger = logging.getLogger("telegram")
            _annoying_logger.setLevel(logging.INFO)
        except telegram.TelegramError as e:
            self._logger.warning('Fail to start BOT. Error %s' % e)
            raise ImportError

        self._logger.debug('Registering on events')
        try:
            self._bot_update.dispatcher.add_handler(telegram.ext.CommandHandler('start', self.response.start))
            self._bot_update.dispatcher.add_handler(telegram.ext.CommandHandler('help', self.response.help))
            self._bot_update.dispatcher.add_handler(telegram.ext.CommandHandler('get_picture', self.response.get_picture))
            self._bot_update.dispatcher.add_handler(telegram.ext.CommandHandler('get_weather', self.response.get_weather))

            # Unknown command
            self._bot_update.dispatcher.add_handler(telegram.ext.MessageHandler(telegram.ext.Filters.command, self.response.unknown))
        except telegram.TelegramError as e:
            self._logger.warning('Fail to register on events. Error %s' % e)
            raise ImportError

        self._logger.debug("Starting periodic update thread")
        try:
            self._bot_update.start_polling()
        except telegram.TelegramError as e:
            self._logger.warning('Fail to start periodic update thread with error %s' % e)
            raise ImportError

        self._logger.info('Telegram bot module ready')

    def __del__(self):
        self._logger.info('Stop Telegram module')
        self._bot_update.stop()


class TelegramCommandHandlers:
    version = '1.0.0.0'
    description = 'Telegram command handlers'

    def __init__(self):
        dispatcher.connect(self._weather_update, signal='WeatherUpdate', sender=dispatcher.Any)
        self._update_lock = threading.Lock()
        self._weather = "Updating please wait"
        self._camera = picamera.PiCamera()

    def start(self, bot, update):
        update.message.reply_text("Hello %s. I'm Aria your digital assistant" % update.message.from_user.first_name)

    def help(self, bot, update):
        update.message.reply_text("Supported command /get_picture and /get_weather")

    def get_picture(self, bot, update):
        self._camera.capture('test.jpg')
        bot.send_photo(chat_id=update.message.chat_id, photo=open('test.jpg', 'rb'))

    def get_weather(self, bot, update):
        self._update_lock.acquire()
        update.message.reply_text(self._weather)
        self._update_lock.release()

    def unknown(self, bot, update):
        bot.send_message(chat_id=update.message.chat_id, text="Sorry, I didn't understand that command.")

    def _weather_update(self, description, temp, wind, icon):
        self._update_lock.acquire()
        self._weather = "Current weather: %s with temperature %02.1f and wind %s" % (description,
                                                                                    temp,
                                                                                    wind)
        self._update_lock.release()
