## @file
## @brief Telegram Bot plugin

import ConfigParser
import logging
import threading
import time
import datetime
import json
import random
from uuid import uuid4

import telegram.ext
import telegram
from emoji import emojize

import picamera

import keyring
from pydispatch import dispatcher


class TelegramBot:
    version = '1.0.0.0'
    description = 'Telegram bot'

    def __init__(self):
        self.gui_status = str(uuid4())
        self._shutdown = threading.Event()
        self._user_status = dict()
        self._update_lock = threading.Lock()

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
            api_user = self._config.get('API', 'user')
            login_name = self._config.get('API', 'login')

            with open("./configuration/telegram_messages.json", "r") as data_file:
                self.response = json.load(data_file)

        except ConfigParser.Error as e:
            self._logger.error('Fail to read configuration file with error %s.Module unload' % e)
            raise ImportError
        except (IOError, ValueError) as e:
            self._logger.error('Fail to read data file with error %s.Module unload' % e)
            raise ImportError

        try:
            self.api_key = keyring.get_password(api_system, api_user)
            self._authorization_password = keyring.get_password(api_system, login_name)
        except keyring.errors as e:
            self._logger.warning('Fail to read Telegram access token with error: %s. Refer to manual. Module unload' % e)
            raise ImportError

        if self.api_key is None or self._authorization_password is None:
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

        self._bot_update.dispatcher.add_handler(telegram.ext.CommandHandler("start", self.start))
        self._bot_update.dispatcher.add_handler(telegram.ext.CommandHandler("help", self.help))
        self._bot_update.dispatcher.add_handler(telegram.ext.CommandHandler("get_weather", self.get_weather))
        self._bot_update.dispatcher.add_handler(telegram.ext.CommandHandler("get_picture", self.get_picture))

        # Unknown command
        self._bot_update.dispatcher.add_handler(
            telegram.ext.MessageHandler(telegram.ext.Filters.text, self.text_handler))

        # Unknown command
        self._bot_update.dispatcher.add_handler(
            telegram.ext.MessageHandler(telegram.ext.Filters.text, self.text_handler))

        # Security camera
        self._camera = picamera.PiCamera()

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

    def start(self, bot, update):
        if 6 <= datetime.datetime.now().hour < 12:
            message = random.choice(self.response['welcome_morning'])
        elif 12 <= datetime.datetime.now().hour < 18:
            message = random.choice(self.response['welcome_afternoon'])
        elif 18 <= datetime.datetime.now().hour < 18:
            message = random.choice(self.response['welcome_evening'])
        else:
            message = random.choice(self.response['welcome_night'])
        update.message.reply_text(message)
        if update.effective_user.id not in self._user_status:
            # new user
            self._logger.info("New user login - Name %s, ID-%s" % (update.effective_user.full_name,
                                                                   update.effective_user.id))
            self._user_status[update.effective_user.id] = {"authorized": False,
                                                           "active_state":None}
            update.message.reply_text(random.choice(self.response['authorization_require']))

    def help(self, bot, update):
        update.message.reply_text("Supported command /get_picture and /get_weather")

    def if_authorized(self, user_id, update):
        if user_id in self._user_status and self._user_status[user_id]["authorized"]:
            self._logger.debug('User %s authorized' % user_id)
            return True
        else:
            self._logger.debug('User %s NOT authorized' % user_id)
            update.message.reply_text(random.choice(self.response['authorization_require']))
            return False

    def text_handler(self, bot, update):
        print
        if update.effective_user.id not in self._user_status:
            # new user
            self._logger.info("New user login - Name %s, ID-%s" % (update.effective_user.full_name,
                                                                   update.effective_user.id))
            self._user_status[str(update.effective_user.id)] = {"authorized": False,
                                                                "active_state": self.authorize}
            update.message.reply_text(random.choice(self.response['authorization_require']))
        elif not self._user_status[update.effective_user.id]["authorized"]:
            # Check password
            if str(update.message.text).replace(' ', '') == self._authorization_password:
                self._logger.info('User %s (id-%s) pass authorization process' % (update.effective_user.full_name,
                                                                                  update.effective_user.id))
                update.message.reply_text(random.choice(self.response['authorization_successful']))
                self._user_status[update.effective_user.id]["authorized"] = True
            else:
                self._logger.info('User %s (id-%s) fail to pass authorization process' %
                                  (update.effective_user.full_name, update.effective_user.id))
                update.message.reply_text(random.choice(self.response['authorization_fail']))
        elif self._user_status[update.effective_user.id]["active_state"] == "city_name":
            custom_keyboard = [['Today'], ['Tomorrow']]
            reply_markup = telegram.ReplyKeyboardMarkup(custom_keyboard)
            update.message.reply_text(text="Select when forecast is needed", reply_markup=reply_markup)
            self._user_status[update.effective_user.id]["active_state"] = "weather_time"
            self._user_status[update.effective_user.id]["weather_city"] = update.message.text
        elif self._user_status[update.effective_user.id]["active_state"] == "weather_time":
            reply_markup = telegram.ReplyKeyboardRemove()
            update.message.reply_text(text="Few seconds - getting forecast. City %s for %s" %
                                           (self._user_status[update.effective_user.id]["weather_city"],
                                            update.message.text), reply_markup=reply_markup)
            if str(update.message.text) == "Tomorrow":
                dispatcher.send(signal='WeatherRequest',
                                callback=self._weather_update, custom_object=update, request_time='tomorrow',
                                request_city=self._user_status[update.effective_user.id]["weather_city"])
            else:
                dispatcher.send(signal='WeatherRequest',
                                callback=self._weather_update, custom_object=update, request_time='today',
                                request_city=self._user_status[update.effective_user.id]["weather_city"])
            self._user_status[update.effective_user.id]["active_state"] = None
        else:
            print update.message.text

    def get_picture(self, bot, update):
        if not self.if_authorized(update.effective_user.id, update):
            return
        self._camera.capture('test.jpg')
        bot.send_photo(chat_id=update.message.chat_id, photo=open('test.jpg', 'rb'))

    def get_weather(self, bot, update):
        if not self.if_authorized(update.effective_user.id, update):
            return
        update.message.reply_text("Where you want know the weather? Write down a city name")
        self._user_status[update.effective_user.id]["active_state"] = "city_name"

    def unknown(self, bot, update):
        bot.send_message(chat_id=update.message.chat_id, text="Sorry, I didn't understand that command.")

    def _weather_update(self, custom, description, temp, wind, icon):
        if description == "Error":

            custom.message.reply_text(emojize(":sob: Sorry, we have some error getting weather", use_aliases=True))
        else:
            if "clear" in str(description).lower():
                custom.message.reply_text(emojize(":sunny: Weather is %s with temperature %02.1fC and wind %s" %
                                                  (description, temp, wind), use_aliases=True))
            elif "cloud" in str(description).lower():
                custom.message.reply_text(emojize(":cloud: Weather is %s with temperature %02.1fC and wind %s" %
                                                  (description, temp, wind), use_aliases=True))
            elif "rain" in str(description).lower():
                custom.message.reply_text(emojize(":umbrella: Weather is %s with temperature %02.1fC and wind %s" %
                                                  (description, temp, wind)))
            else:
                custom.message.reply_text(emojize(":earth_africa: Weather is %s with temperature %02.1fC and wind %s" %
                                                  (description, temp, wind), use_aliases=True))

