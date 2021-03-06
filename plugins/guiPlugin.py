# coding=utf-8
## @file
## @brief GUIModule
## @details Contain all gui function
## @par Configuration file
## @verbinclude ./configuration/gui.conf
#
import ConfigParser
import logging
from pydispatch import dispatcher
import os
import time
import datetime
import threading
from scipy import misc
import numpy as np
import keyring
import urllib
import json
import facebook

import wx


## @class Gui
## @brief Main GUI
## @details Create GUI interface with Facebook profile pictures
## @see https://developers.facebook.com/tools/explorer/145634995501895/?method=GET&path=&version=v2.7
## @version 1.0.0.0
class Gui(wx.Frame):
    ## @brief Create GUI based on wx python
    ## @details Create and initialize instance start fetching and periodic update threads
    ## @exception ImportError Configuration or IO system error - Module will be unloaded.
    ## @par Registering on events:
    # GuiNotification - User speech input.\n
    # SayText - System to user response text.\n
    # SpeechRecognize - User to system text.\n
    # WeatherUpdate - Periodic weather update.\n
    #
    ## @see SttPlugin
    ## @see WeatherPlugin
    ## @see AudioSubSystem
    def __init__(self, *args, **kwds):
        ## @brief Shutdown flag - notify to threads exits
        self._shutdown = threading.Event()
        ## @brief GUI synchronization - avoid GUI update from different threads
        self._gui_update_lock = threading.Lock()
        ## @brief dictionary of notification icons and their owners
        self._notification_tray = {}
        try:
            self._logger = logging.getLogger('moduleGui')
        except ConfigParser.NoSectionError as e:
            print 'Fatal error  - fail to set logger.Error: %s ' % e.message
            raise ImportError
        self._logger.debug('GUI logger started')

        # Reading config file
        try:
            self._config = ConfigParser.SafeConfigParser(allow_no_value=False)
            self._config.read('./configuration/gui.conf')
            api_system = self._config.get('API', 'system')
            api_user = self._config.get('API', 'user')
            try:
                self.api_key = keyring.get_password(api_system, api_user)
            except keyring.errors as e:
                self._logger.warning(
                    'Fail to read Facebook token with error: %s. Refer to manual. Module unload' % e)
                raise ImportError
            if self.api_key is None:
                self._logger.warning('Fail to read Facebook token. Refer to manual. Module unload')
                raise ImportError
            self._animation_steps = self._config.getint('General', 'animation_steps')
            self._clear_delay = self._config.getint('General', 'clear_after')
            self._change_after = self._config.getint('General', 'change_after')
            self._animation_speed = self._config.getfloat('General', 'animation_speed')

            self._ignore_albums = self._config.get('Facebook', 'Skip_albums')
            self._ignore_albums.split(';')

            self._animation_active = self._config.getboolean('General', 'animation')

            self._temp_folder = self._config.get('General', 'temp_folder')
            if not os.path.exists(self._temp_folder):
                try:
                    os.makedirs(self._temp_folder)
                except IOError as e:
                    self._logger.error('Fail to temporary folder with error %s.Module unload' % e)
                    raise ImportError
        except ConfigParser.Error as e:
            self._logger.error('Fail to read configuration file with error %s.Module unload' % e)
            raise ImportError

        # begin wxGlade: Gui.__init__
        # kwds["style"] = kwds.get("style", 0) | wx.FRAME_TOOL_WINDOW | wx.STAY_ON_TOP
        kwds["style"] = kwds.get("style", 0) 
        wx.Frame.__init__(self, *args, **kwds)
        self.SetSize((800, 510))
        
        # Controls
        self._animation_circle_bmp = None
        self._system_response_bmp = None

        self._system_response_lbl = None
        self._user_request_lbl = None

        self._clock_lbl = None
        self._date_lbl = None

        self.weather_desc_lbl = None
        self._weather_temp_lbl = None
        self.weather_wind_lbl = None
        self._weather_icon = None

        self._main_picture_bmp = None

        self._notification_slots = []

        self.__set_properties()
        self.__do_layout()
        # end wxGlade
        # Microphone activity
        self._logger.debug('Registering on events')
        try:
            dispatcher.connect(self._notification, signal='GuiNotification', sender=dispatcher.Any)
            dispatcher.connect(self._system_response_text, signal='SayText', sender=dispatcher.Any)
            dispatcher.connect(self._user_request_text, signal='SpeechRecognize', sender=dispatcher.Any)
            dispatcher.connect(self._weather_display, signal='WeatherUpdate', sender=dispatcher.Any)
        except dispatcher.DispatcherTypeError as e:
            self._logger.error('Fail to subscribe on event with error %s.Module unload' % e)
            raise ImportError

        self._logger.info('Starting animation and update threads')
        try:
            threading.Thread(target=self._animation_update).start()
            threading.Thread(target=self._time_update).start()
            if self._animation_active:
                threading.Thread(target=self.main_pic_animation).start()
            else:
                self._logger.info('Animation disabled')
        except Exception as e:
            self._logger.error('Fail to start thread with error %s.Module unload' % e)
            raise ImportError

    ## @brief Stop module
    ## @details Stop all module thread and sub-programs
    def __del__(self):
        self._logger.info('Module unload')
        self._shutdown.set()
        self.Destroy()

    ## @brief Set GUI properties
    ## @details Update GUI elements and their properties
    ## @note This function generated create be WxGlade
    ## @warning This function should not be called from outside
    def __set_properties(self):
        # begin wxGlade: Gui.__set_properties
        self.SetTitle("Aria")
        # end wxGlade

    ## @brief Set GUI layout
    ## @details Update GUI elements and their layouts
    ## @note This function generated create be WxGlade
    ## @warning This function should not be called from outside
    def __do_layout(self):
        # begin wxGlade: Gui.__do_layout
        sizer_1 = wx.BoxSizer(wx.VERTICAL)
        sizer_4 = wx.BoxSizer(wx.VERTICAL)
        sizer_6 = wx.BoxSizer(wx.HORIZONTAL)
        sizer_5 = wx.BoxSizer(wx.HORIZONTAL)
        sizer_2 = wx.BoxSizer(wx.HORIZONTAL)
        sizer_7 = wx.BoxSizer(wx.VERTICAL)
        sizer_8 = wx.BoxSizer(wx.VERTICAL)
        sizer_10 = wx.BoxSizer(wx.HORIZONTAL)
        sizer_9 = wx.BoxSizer(wx.HORIZONTAL)
        sizer_3 = wx.BoxSizer(wx.VERTICAL)
        self._animation_circle_bmp = wx.StaticBitmap(self, wx.ID_ANY, wx.Bitmap("./plugins/Icons/Load/frame-0.png", wx.BITMAP_TYPE_ANY))
        self._animation_circle_bmp.SetMinSize((25, 25))
        sizer_3.Add(self._animation_circle_bmp, 0, 0, 0)
        for i in range(15):
            data_slot = wx.StaticBitmap(self, wx.ID_ANY, wx.Bitmap("./plugins/Icons/empty.png", wx.BITMAP_TYPE_ANY))
            data_slot.SetMinSize((25, 25))
            sizer_3.Add(data_slot, 0, 0, 0)
            self._notification_slots.append(data_slot)
        sizer_2.Add(sizer_3, 0, wx.ALIGN_CENTER | wx.EXPAND, 0)
        self._main_picture_bmp = wx.StaticBitmap(self, wx.ID_ANY,
                                                 wx.Bitmap("./plugins/Icons/login.png", wx.BITMAP_TYPE_ANY))
        self._main_picture_bmp.SetMinSize((630, 430))
        sizer_2.Add(self._main_picture_bmp, 0, 0, 0)
        self._clock_lbl = wx.StaticText(self, wx.ID_ANY, "", style=wx.ALIGN_CENTER)
        self._clock_lbl.SetMinSize((115, 55))
        self._clock_lbl.SetFont(wx.Font(35, wx.DEFAULT, wx.NORMAL, wx.LIGHT, 0, "Ubuntu"))
        sizer_7.Add(self._clock_lbl, 0, 0, 0)
        self._date_lbl = wx.StaticText(self, wx.ID_ANY, "")
        self._date_lbl.SetMinSize((123, 30))
        self._date_lbl.SetFont(wx.Font(20, wx.DEFAULT, wx.NORMAL, wx.LIGHT, 0, ""))
        sizer_7.Add(self._date_lbl, 0, 0, 0)
        self.weather_desc_lbl = wx.StaticText(self, wx.ID_ANY, "Updating ...")
        self.weather_desc_lbl.SetMinSize((160, 25))
        sizer_8.Add(self.weather_desc_lbl, 0, 0, 0)
        self._weather_icon = wx.StaticBitmap(self, wx.ID_ANY,
                                             wx.Bitmap("./plugins/Icons/weather_none.png", wx.BITMAP_TYPE_ANY))
        self._weather_icon.SetMinSize((50, 50))
        sizer_9.Add(self._weather_icon, 0, 0, 0)
        self._weather_temp_lbl = wx.StaticText(self, wx.ID_ANY, "", style=wx.ALIGN_RIGHT)
        # self._weather_temp_lbl.SetMinSize((80, 50))
        self._weather_temp_lbl.SetFont(wx.Font(20, wx.DEFAULT, wx.NORMAL, wx.NORMAL, 0, "Noto Sans"))
        sizer_9.Add(self._weather_temp_lbl, 0, 0, 0)
        sizer_8.Add(sizer_9, 0, 0, 0)
        self.weather_wind_lbl = wx.StaticText(self, wx.ID_ANY, "", style=wx.ALIGN_CENTER)
        self.weather_wind_lbl.SetMinSize((145, 50))
        sizer_10.Add(self.weather_wind_lbl, 0, wx.ALL, 1)
        sizer_8.Add(sizer_10, 0, 0, 0)
        sizer_8.Add((0, 0), 0, 0, 0)
        sizer_8.Add((0, 0), 0, 0, 0)
        sizer_7.Add(sizer_8, 0, 0, 0)
        sizer_2.Add(sizer_7, 1, wx.EXPAND, 0)
        sizer_1.Add(sizer_2, 1, wx.EXPAND, 0)
        self._user_request_lbl = wx.StaticText(self, wx.ID_ANY, "", style=wx.ALIGN_RIGHT)
        self._user_request_lbl.SetMinSize((765, 25))
        sizer_5.Add(self._user_request_lbl,  1, wx.EXPAND, 0)
        bitmap_9 = wx.StaticBitmap(self, wx.ID_ANY, wx.Bitmap("./plugins/Icons/user.png", wx.BITMAP_TYPE_ANY))
        bitmap_9.SetMinSize((25, 25))
        sizer_5.Add(bitmap_9, 0, wx.EXPAND, 0)
        sizer_4.Add(sizer_5, 1, wx.EXPAND, 0)
        self._system_response_bmp = wx.StaticBitmap(self, wx.ID_ANY,
                                                    wx.Bitmap("./plugins/Icons/response_good.png", wx.BITMAP_TYPE_ANY))
        self._system_response_bmp.SetMinSize((25, 25))
        sizer_6.Add(self._system_response_bmp, 0, 0, 0)
        self._system_response_lbl = wx.StaticText(self, wx.ID_ANY, "", style=wx.ALIGN_LEFT)
        self._system_response_lbl.SetMinSize((765, 25))
        sizer_6.Add(self._system_response_lbl, 0, wx.ALIGN_CENTER | wx.ALL, 0)
        sizer_4.Add(sizer_6, 1, wx.EXPAND, 0)
        sizer_1.Add(sizer_4, 1, wx.EXPAND, 0)
        self.SetSizer(sizer_1)
        self.Layout()
        self.Centre()
        # end wxGlade

    ## @brief GUI element update
    ## @details Thread safe GUI update
    ## @param func - WxPython function
    ## @param data - Configuration data for WxPython update function
    def safe_update(self, func, data):
        self._gui_update_lock.acquire()
        func(data)
        self._gui_update_lock.release()

    ## @brief Wrapper for delayed GUI update
    ## @details Thread safe GUI update with delay
    ## @param func - WxPython function
    ## @param data - Configuration data for WxPython update function
    def safe_update_delay(self, func, data):
        threading.Thread(target=self._safe_update_delay, args=(func, data)).start()

    ## @brief Delayed GUI update
    ## @details Thread safe GUI update with delay
    ## @param func - WxPython function
    ## @param data - Configuration data for WxPython update function
    def _safe_update_delay(self, func, data):
        time.sleep(self._clear_delay)
        wx.CallAfter(self.safe_update, func, data)

    ## @brief Wrapper for tray update
    ## @details Thread safe tray update
    ## @param source - Unique id of caller
    ## @param icon_path - Relative path of icon for tray
    def _notification(self, source, icon_path):
        if source in self._notification_tray:
            if icon_path == '':
                self._logger.debug('Removing notification from %s' % source)
                wx.CallAfter(self.safe_update, self._notification_tray[source].SetBitmap,
                             wx.Bitmap('./plugins/Icons/empty.png', wx.BITMAP_TYPE_ANY))
                self._notification_slots.insert(0, self._notification_tray[source])
                del self._notification_tray[source]
            else:
                self._logger.debug('Updating notification tray - source %s, icon - %s' % (source, icon_path))
                wx.CallAfter(self.safe_update, self._notification_tray[source].SetBitmap,
                             wx.Bitmap(os.path.join('./plugins/Icons/', icon_path), wx.BITMAP_TYPE_ANY))
        else:
            if len(self._notification_slots) == 0:
                self._logger.warning('No free notification slots')
                return
            self._notification_tray[source] = self._notification_slots[0]
            self._notification_slots = self._notification_slots[1:]
            wx.CallAfter(self.safe_update, self._notification_tray[source].SetBitmap,
                         wx.Bitmap(os.path.join('./plugins/Icons/', icon_path), wx.BITMAP_TYPE_ANY))

    ## @brief Main picture animation
    ## @details Create slow change effect of main picture
    ## @warning This function should not be called from outside
    ## @bug This function may cause high CPU load
    def _animation_update(self):
        bitmaps = []
        for single in range(30):
            bitmaps.append(wx.Bitmap("./plugins/Icons/Load/frame-%i.png" % single, wx.BITMAP_TYPE_ANY))
        while not self._shutdown.isSet():
            for single_frame in bitmaps:
                time.sleep(self._animation_speed)
                wx.CallAfter(self.safe_update, self._animation_circle_bmp.SetBitmap, single_frame)

    ## @brief Wrapper for SayText event
    ## @details Write TTS input text on screen with typing animation
    ## @param text - Text to TTS engine
    def _system_response_text(self, text):
        for stop_char in range(len(text) + 1):
            time.sleep(0.05)
            wx.CallAfter(self.safe_update, self._system_response_lbl.SetLabel, text[:stop_char])
        self.safe_update_delay(self._system_response_lbl.SetLabel, "")

    ## @brief Wrapper for SpeechRecognize event
    ## @details Write STT output text on screen with typing animation
    ## @param entities - Ignored
    ## @param raw_text - Text from STT engine
    def _user_request_text(self, entities, raw_text):
        for stop_char in range(len(raw_text) + 1):
            time.sleep(0.05)
            wx.CallAfter(self.safe_update, self._user_request_lbl.SetLabel, "%150s" % raw_text[:stop_char])
        self.safe_update_delay(self._user_request_lbl.SetLabel, "")

    ## @brief Time update
    ## @details Update Time, and Date in GUI window
    def _time_update(self):
        while not self._shutdown.isSet():
            curr_time = datetime.datetime.now()
            time.sleep(1)
            wx.CallAfter(self.safe_update, self._clock_lbl.SetLabel, "%02d:%02d" % (curr_time.hour, curr_time.minute))
            wx.CallAfter(self.safe_update, self._date_lbl.SetLabel, "%02d/%02d/%02d" %
                         (curr_time.day, curr_time.month, curr_time.year % 100))

    ## @brief Wrapper for WeatherUpdate event
    ## @details Display weather info in GUI
    ## @param description - Short weather description
    ## @param temp - Current temperature
    ## @param wind - Short wind description
    ## @param icon Path to weather icon. Provided by OpenWeatherMap
    def _weather_display(self, description, temp, wind, icon):
        wx.CallAfter(self.safe_update, self.weather_desc_lbl.SetLabel, description)
        wx.CallAfter(self.safe_update, self._weather_temp_lbl.SetLabel, "%02.1fC" % temp)
        wx.CallAfter(self.safe_update, self.weather_wind_lbl.SetLabel, "Wind: %s" % str(wind).replace(' ', '\n'))
        wx.CallAfter(self.safe_update, self._weather_icon.SetBitmap, wx.Bitmap(icon, wx.BITMAP_TYPE_ANY))

    ## @brief Download image from Facebook
    ## @details Download image for future processing (animation). Small images and ignored albums ignored
    ## @bug Due to policy of Facebook application without server may use only short period access token
    def main_pic_animation(self):
        # TODO Add NORMAL access
        prev_pic = misc.imread("./plugins/Icons/login.png", False, 'RGB')
        prev_pic = misc.imresize(prev_pic, (430, 600))
        self._logger.debug('Requesting albums and photos from Facebook')
        graph = facebook.GraphAPI(access_token=self.api_key, version="2.7")
        while True:
            facebook_json = graph.get_object(id='me', fields='albums.fields(name,photos.fields(source))')
            for album in facebook_json['albums']['data']:
                if album['name'] in self._ignore_albums:
                    self._logger.debug("Skipping album %s" % album['name'])
                    continue
                else:
                    self._logger.debug("Reading picture from album %s" % album['name'])
                for photo in album['photos']['data']:
                    # Download
                    self._logger.debug('Download next picture')
                    urllib.urlretrieve(photo['source'], os.path.join(self._temp_folder, "next.jpg"))
                    next_pic = misc.imread(os.path.join(self._temp_folder, "next.jpg"), False, 'RGB')
                    if 0.4 < (next_pic.shape[0] / float(next_pic.shape[1])) < 1:
                        next_pic = misc.imresize(next_pic, (430, 600))
                        for i in range(0, 101, self._animation_steps):
                            pic3 = ((i * next_pic.astype(np.int32) + (100 - i) * prev_pic.astype(np.int32)) / 100)
                            misc.imsave(os.path.join(self._temp_folder, "slice_%03d.png" % i),
                                        misc.imresize(pic3, (430, 630)))
                        for i in range(0, 101, self._animation_steps):
                            wx.CallAfter(self.safe_update, self._main_picture_bmp.SetBitmap,
                                         wx.Bitmap(os.path.join(self._temp_folder, "slice_%03d.png" % i),
                                                   wx.BITMAP_TYPE_ANY))
                            time.sleep(self._animation_speed)
                        prev_pic = next_pic
                        os.remove(os.path.join(self._temp_folder, "next.jpg"))
                    else:
                        self._logger.debug('Skipping image due to size, image may be impacted during resize')
                        os.remove(os.path.join(self._temp_folder, "next.jpg"))
                        continue

                    self._shutdown.wait(self._change_after)
                    if self._shutdown.set():
                        return
# end of class Gui


## @class GuiPlugin
## @brief Init wx-python GUI
## @details Create GUI interface
## @version 1.0.0.0
class GuiPlugin:
    ## @brief Plugin version
    version = '1.0.0.0'
    ## @brief Plugin description
    description = 'GUI'

    ## @brief Start GUI
    ## @details Start GUI initialization in thread
    def __init__(self):
        threading.Thread(target=self._gui_thread).start()

    ## @brief Initialize GUI
    ## @details Create GUI frame and continue run in daemon thread mode
    def _gui_thread(self):
        gui = wx.PySimpleApp()
        frame = Gui(None, wx.ID_ANY, "")
        gui.SetTopWindow(frame)
        frame.Show()
        t = threading.Thread(target=gui.MainLoop)
        t.setDaemon(1)
        t.start()

