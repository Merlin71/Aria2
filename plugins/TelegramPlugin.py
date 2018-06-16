## @file
## @brief Telegram Bot plugin
## @package TelegramBot
## @details Create additional User interface using Telegram bot API
## @see https://core.telegram.org/api
## @par Configuration file
## @verbinclude ./configuration/telegram.conf
#
## @par Message file
## @verbinclude ./configuration/telegram_messages.json
#
import ConfigParser
import logging
import threading
import time
import datetime
import json
import random
from uuid import uuid4
import os

from PIL import Image, ImageFont, ImageDraw


import telegram.ext
import telegram
from emoji import emojize

import picamera

import keyring
from pydispatch import dispatcher

## @class TelegramBot
## @brief Additional user interface
## @details Communicate with Telegram servers and generate response base on system status
## @version 1.0.0.0
class TelegramBot:
    ## @brief Plugin version
    version = '1.0.0.0'
    ## @brief Short Plugin description
    description = 'Telegram bot'

    ## @brief Start telegram plugin
    ## @details Create and initialize instance start fetching messages. Allow interaction with camera
    ## @exception ImportError Configuration or IO system error - Module will be unloaded.
    ## @par Generate events:
    # GuiNotification - User speech input.\n
    # WeatherRequest - Request custom weather forecast.\n
    # SayText - Generate voice message using TtsPluign
    #
    ## @see TTS
    ## @see WeatherPlugin
    ## @see AudioSubSystem
    def __init__(self):
        ## @brief Unique id for GUI tray icon - message received
        self._notify_gui_status = str(uuid4())
        ## @brief Unigue id for GUI tray icon - camera usage
        self._camera_gui_status = str(uuid4())
        ## @brief Notify to all thread exit
        self._shutdown = threading.Event()
        ## @brief User status dictionary (Login, autorization, dialog state)
        self._user_status = dict()
        ## @brief syncronization event - Allow GUI update
        self._activity_event = threading.Event()

        try:
            ## @brief looger instance
            self._logger = logging.getLogger('moduleTelegram')
        except ConfigParser.NoSectionError as e:
            print 'Fatal error  - fail to set logger.Error: %s ' % e.message
            raise ImportError
        self._logger.debug('Telegram bot logger started')
        # Reading config file
        try:
            ## @brief config file instance
            self._config = ConfigParser.SafeConfigParser(allow_no_value=False)
            self._config.read('./configuration/telegram.conf')
            api_system = self._config.get('API', 'system')
            api_user = self._config.get('API', 'user')
            login_name = self._config.get('API', 'login')
            ## @brief Rotation angle of camera picture
            self._camera_angle = self._config.getfloat('Camera', 'angle')

            with open("./configuration/telegram_messages.json", "r") as data_file:
                ## @brief Response messages dictionary
                self.response = json.load(data_file)

        except ConfigParser.Error as e:
            self._logger.error('Fail to read configuration file with error %s.Module unload' % e)
            raise ImportError
        except (IOError, ValueError) as e:
            self._logger.error('Fail to read data file with error %s.Module unload' % e)
            raise ImportError

        try:
            ## @brief Telegram API key
            self.api_key = keyring.get_password(api_system, api_user)
            ## @brief User authorization password
            self._authorization_password = keyring.get_password(api_system, login_name)
        except keyring.errors as e:
            self._logger.warning('Fail to read Telegram access token with error: %s. Refer to manual. Module unload' % e)
            raise ImportError

        if self.api_key is None or self._authorization_password is None:
            self._logger.warning('Fail to read Telegram access token. Refer to manual. Module unload')
            raise ImportError

        self._logger.info('Starting new Bot service')
        try:
            ## @brief Bot instance
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
        self._bot_update.dispatcher.add_handler(telegram.ext.CommandHandler("say", self.say_text))

        # Unknown command
        self._bot_update.dispatcher.add_handler(
            telegram.ext.MessageHandler(telegram.ext.Filters.text, self.text_handler))

        # Unknown command
        self._bot_update.dispatcher.add_handler(
            telegram.ext.MessageHandler(telegram.ext.Filters.text, self.text_handler))

        ## @brief Path to temp folder
        self._temp_folder = self._config.get('System', 'temp_folder')
        if not os.path.exists(self._temp_folder):
            try:
                os.makedirs(self._temp_folder)
            except IOError as e:
                self._logger.error('Fail to temporary folder with error %s.Module unload' % e)
                raise ImportError

        ## @brief Security camera instance
        self._camera = picamera.PiCamera()

        self._logger.debug("Starting periodic update thread")
        try:
            self._bot_update.start_polling()
        except telegram.TelegramError as e:
            self._logger.warning('Fail to start periodic update thread with error %s' % e)
            raise ImportError

        threading.Thread(target=self._activity_update).start()

        self._logger.info('Telegram bot module ready')
        
    ## @brief Stop module
    ## @details Stop all module thread and sub-programs
    def __del__(self):
        self._logger.info('Stop Telegram module')
        self._bot_update.stop()

    ## @brief Update GUI tray according user activity
    ## @details Receive event flag and set/clear telegram icon in GUI tray
    ## @see guiPlugin
    def _activity_update(self):
        while not self._shutdown.isSet():
            if self._activity_event.wait(10):
                dispatcher.send(signal='GuiNotification', source=self._notify_gui_status, icon_path="telegram.png")
                self._activity_event.clear()
            else:
                dispatcher.send(signal='GuiNotification', source=self._notify_gui_status, icon_path="")

    ## @brief Event wrapper of start command
    ## @details Send welcome text and create/reset user instance
    ## @param bot Bot object
    ## @param update Chat update object
    def start(self, bot, update):
        self._activity_event.set()
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

    ## @brief Event wrapper of help command
    ## @details Send welcome help text
    ## @param bot Bot object
    ## @param update Chat update object
    def help(self, bot, update):
        self._activity_event.set()
        update.message.reply_text("Supported command /get_picture and /get_weather")

    ## @brief Check user authorization
    ## @details Check if user pass authorization process
    ## @return True/False according user status
    def if_authorized(self, user_id, update):
        if user_id in self._user_status and self._user_status[user_id]["authorized"]:
            self._logger.debug('User %s authorized' % user_id)
            return True
        else:
            self._logger.debug('User %s NOT authorized' % user_id)
            update.message.reply_text(random.choice(self.response['authorization_require']))
            return False

    ## @brief Event wrapper user text messages
    ## @details Update user dialog status
    ## @param bot Bot object
    ## @param update Chat update object
    ## @par Generate events:
    # WeatherRequest - Weather forecast request
    # SayText - Generate speech using Tts engine
    #
    ## @see weatherPlugin
    ## see TTS
    def text_handler(self, bot, update):
        self._activity_event.set()
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
            custom_keyboard = [['Today'], ['Tomorrow'], []]
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
        elif self._user_status[update.effective_user.id]["active_state"] == "say_text":
            dispatcher.send(signal='SayText', text=update.message.text)
        else:
            print update.message.text

    ## @brief Event wrapper of say_text command
    ## @details Receive command and update user dialog status
    ## @param bot Bot object
    ## @param update Chat update object
    def say_text(self, bot, update):
        self._activity_event.set()
        if not self.if_authorized(update.effective_user.id, update):
            return
        update.message.reply_text("What do you want that I say ?")
        self._user_status[update.effective_user.id]["active_state"] = "say_text"

    ## @brief Event wrapper for get_picture command
    ## @details Receive command and send picture from security camera
    ## @param bot Bot object
    ## @param update Chat update object
    def get_picture(self, bot, update):
        self._activity_event.set()
        if not self.if_authorized(update.effective_user.id, update):
            return
        dispatcher.send(signal='GuiNotification', source=self._camera_gui_status, icon_path="camera.png")
        self._camera.capture(os.path.join(self._temp_folder, "raw.jpg"))
        raw_pic = Image.open(os.path.join(self._temp_folder, "raw.jpg"))
        post_img = raw_pic.rotate(self._camera_angle, expand=True)
        draw = ImageDraw.Draw(post_img)
        font = ImageFont.load_default()
        draw.text((0, 0), str(datetime.datetime.now()), (255, 255, 255), font=font)

        post_img.save(os.path.join(self._temp_folder, "process.jpg"))
        bot.send_photo(chat_id=update.message.chat_id, photo=open(os.path.join(self._temp_folder, "process.jpg"), 'rb'))
        dispatcher.send(signal='GuiNotification', source=self._camera_gui_status, icon_path="")

    ## @brief Event wrapper for get_weather command
    ## @details Receive command and request weather forecast
    ## @param bot Bot object
    ## @param update Chat update object
    ## @see weatherPlugin
    def get_weather(self, bot, update):
        self._activity_event.set()
        if not self.if_authorized(update.effective_user.id, update):
            return
        update.message.reply_text("Where you want know the weather? Write down a city name")
        self._user_status[update.effective_user.id]["active_state"] = "city_name"

    ## @brief Event wrapper for unknow command
    ## @details Receive command and response to user
    ## @param bot Bot object
    ## @param update Chat update object
    def unknown(self, bot, update):
        self._activity_event.set()
        bot.send_message(chat_id=update.message.chat_id, text="Sorry, I didn't understand that command.")

    ## @brief Callback function of weather forecast request
    ## @details Replay to user weather forecast
    ## @param custom Indification object
    ## @param description Short weather descritpion
    ## @param temp Temperature
    ## @param wind Short Wind description
    ## @param icon Path to weather icon - Ignored
    def _weather_update(self, custom, description, temp, wind, icon):
        if description == "Error":

            custom.message.reply_text(emojize(":sob: Sorry, we have some error getting weather", use_aliases=True))
        else:
            if "clear" in str(description).lower():
                custom.message.reply_text(emojize(":sunny: Weather is %s with temperature %02.1fC and %s" %
                                                  (description, temp, wind), use_aliases=True))
            elif "cloud" in str(description).lower():
                custom.message.reply_text(emojize(":cloud: Weather is %s with temperature %02.1fC and %s" %
                                                  (description, temp, wind), use_aliases=True))
            elif "rain" in str(description).lower():
                custom.message.reply_text(emojize(":umbrella: Weather is %s with temperature %02.1fC and %s" %
                                                  (description, temp, wind)))
            else:
                custom.message.reply_text(emojize(":earth_africa: Weather is %s with temperature %02.1fC and %s" %
                                                  (description, temp, wind), use_aliases=True))

