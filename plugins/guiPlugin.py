# coding=utf-8
## @file
## @brief GUI plugin
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
class Gui(wx.Frame):
    def __init__(self, *args, **kwds):
        self._error_msg = threading.Event()
        self._unclear_msg = threading.Event()
        self._shutdown = threading.Event()
        self._gui_update_lock = threading.Lock()
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
        self._microphone_bmp = None
        self._speaker_bmp = None
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

        # bitmaps
        self._logger.debug('Loading image resources')
        self.microphone_off = wx.Bitmap("./plugins/Icons/microphone_off.png", wx.BITMAP_TYPE_ANY)
        self.microphone_on = wx.Bitmap("./plugins/Icons/microphone_passive.png", wx.BITMAP_TYPE_ANY)
        self.microphone_record = wx.Bitmap("./plugins/Icons/microphone_record.png", wx.BITMAP_TYPE_ANY)

        self.speaker_on = wx.Bitmap("./plugins/Icons/speaking.png", wx.BITMAP_TYPE_ANY)
        self.speaker_off = wx.Bitmap("./plugins/Icons/speaker_off.png", wx.BITMAP_TYPE_ANY)
        self.speaker_analyze = wx.Bitmap("./plugins/Icons/synthesis.png", wx.BITMAP_TYPE_ANY)

        self.system_response_good = wx.Bitmap("./plugins/Icons/response_good.png", wx.BITMAP_TYPE_ANY)
        self.system_response_bad = wx.Bitmap("./plugins/Icons/response_bad.png", wx.BITMAP_TYPE_ANY)
        self.system_response_error = wx.Bitmap("./plugins/Icons/response_fail.png", wx.BITMAP_TYPE_ANY)

        self.__set_properties()
        self.__do_layout()
        # end wxGlade
        # Microphone activity
        self._logger.debug('Registering on events')
        try:
            dispatcher.connect(self._detection_status, signal='HotWordDetectionActive', sender=dispatcher.Any)
            dispatcher.connect(self._record_status, signal='RecordActive', sender=dispatcher.Any)
            dispatcher.connect(self._playback_status, signal='PlaybackActive', sender=dispatcher.Any)
            dispatcher.connect(self._synthesize_status, signal='SpeechSynthesize', sender=dispatcher.Any)
            dispatcher.connect(self._system_response_text, signal='SayText', sender=dispatcher.Any)
            dispatcher.connect(self._user_request_text, signal='SpeechRecognize', sender=dispatcher.Any)
            dispatcher.connect(self._say_status_update, signal='SayResponse', sender=dispatcher.Any)
            dispatcher.connect(self._weather_display, signal='WeatherUpdate', sender=dispatcher.Any)
        except dispatcher.DispatcherTypeError as e:
            self._logger.error('Fail to subscribe on event with error %s.Module unload' % e)
            raise ImportError

        self._logger.info('Starting animation and update threads')
        try:
            threading.Thread(target=self._animation_update).start()
            threading.Thread(target=self._time_update).start()
            threading.Thread(target=self.main_pic_animation).start()
        except Exception as e:
            self._logger.error('Fail to start thread with error %s.Module unload' % e)
            raise ImportError

    def __del__(self):
        self._logger.info('Module unload')
        self._shutdown.set()
        
    def __set_properties(self):
        # begin wxGlade: Gui.__set_properties
        self.SetTitle("Aria")
        # end wxGlade

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
        self._microphone_bmp = wx.StaticBitmap(self, wx.ID_ANY, self.microphone_off)
        self._microphone_bmp.SetMinSize((25, 25))
        sizer_3.Add(self._microphone_bmp, 0, 0, 0)
        self._speaker_bmp = wx.StaticBitmap(self, wx.ID_ANY, self.speaker_off)
        self._speaker_bmp.SetMinSize((25, 25))
        sizer_3.Add(self._speaker_bmp, 0, 0, 0)
        bitmap_5 = wx.StaticBitmap(self, wx.ID_ANY, wx.Bitmap("./plugins/Icons/camera_off.png", wx.BITMAP_TYPE_ANY))
        bitmap_5.SetMinSize((25, 25))
        sizer_3.Add(bitmap_5, 0, 0, 0)
        bitmap_6 = wx.StaticBitmap(self, wx.ID_ANY, wx.Bitmap("./plugins/Icons/calendar_free.png", wx.BITMAP_TYPE_ANY))
        bitmap_6.SetMinSize((25, 25))
        sizer_3.Add(bitmap_6, 0, 0, 0)
        bitmap_7 = wx.StaticBitmap(self, wx.ID_ANY, wx.Bitmap("./plugins/Icons/email_empty.png", wx.BITMAP_TYPE_ANY))
        bitmap_7.SetMinSize((25, 25))
        sizer_3.Add(bitmap_7, 0, 0, 0)
        self._animation_circle_bmp0 = wx.StaticBitmap(self, wx.ID_ANY, wx.Bitmap("./plugins/Icons/internet_bad.png", wx.BITMAP_TYPE_ANY))
        self._animation_circle_bmp0.SetMinSize((25, 25))
        sizer_3.Add(self._animation_circle_bmp0, 0, 0, 0)
        sizer_3.Add((0, 0), 0, 0, 0)
        sizer_3.Add((0, 0), 0, 0, 0)
        sizer_3.Add((0, 0), 0, 0, 0)
        sizer_3.Add((0, 0), 0, 0, 0)
        self._animation_circle_bmp1 = wx.StaticBitmap(self, wx.ID_ANY, wx.Bitmap("./plugins/Icons/twitter.png", wx.BITMAP_TYPE_ANY))
        self._animation_circle_bmp1.SetMinSize((25, 25))
        sizer_3.Add(self._animation_circle_bmp1, 0, 0, 0)
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
        self._system_response_bmp = wx.StaticBitmap(self, wx.ID_ANY, self.system_response_good)
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

    def safe_update(self, func, data):
        self._gui_update_lock.acquire()
        func(data)
        self._gui_update_lock.release()

    def safe_update_delay(self, func, data):
        threading.Thread(target=self._safe_update_delay, args=(func, data)).start()

    def _safe_update_delay(self, func, data):
        time.sleep(self._clear_delay)
        wx.CallAfter(self.safe_update, func, data)

    def _animation_update(self):
        bitmaps = []
        for single in range(30):
            bitmaps.append(wx.Bitmap("./plugins/Icons/Load/frame-%i.png" % single, wx.BITMAP_TYPE_ANY))
        while not self._shutdown.isSet():
            for single_frame in bitmaps:
                time.sleep(self._animation_speed)
                wx.CallAfter(self.safe_update, self._animation_circle_bmp.SetBitmap, single_frame)

    def _detection_status(self, status=None):
        if status:
            wx.CallAfter(self.safe_update, self._microphone_bmp.SetBitmap, self.microphone_on)
        else:
            wx.CallAfter(self.safe_update, self._microphone_bmp.SetBitmap, self.microphone_off)

    def _record_status(self, status=None):
        if status:
            wx.CallAfter(self.safe_update, self._microphone_bmp.SetBitmap, self.microphone_record)
        else:
            wx.CallAfter(self.safe_update, self._microphone_bmp.SetBitmap, self.microphone_off)

    def _playback_status(self, status=None):
        if status:
            wx.CallAfter(self.safe_update, self._speaker_bmp.SetBitmap, self.speaker_on)
        else:
            wx.CallAfter(self.safe_update, self._speaker_bmp.SetBitmap, self.speaker_off)

    def _synthesize_status(self, status=None):
        if status:
            wx.CallAfter(self.safe_update, self._speaker_bmp.SetBitmap, self.speaker_analyze)
        else:
            wx.CallAfter(self.safe_update, self._speaker_bmp.SetBitmap, self.speaker_off)

    def _system_response_text(self, text):
        if self._error_msg.isSet():
            wx.CallAfter(self.safe_update, self._system_response_bmp.SetBitmap, self.system_response_error)
            self._error_msg.clear()
        elif self._unclear_msg.isSet():
            wx.CallAfter(self.safe_update, self._system_response_bmp.SetBitmap, self.system_response_bad)
            self._unclear_msg.clear()
        else:
            wx.CallAfter(self.safe_update, self._system_response_bmp.SetBitmap, self.system_response_good)

        for stop_char in range(len(text) + 1):
            time.sleep(0.05)
            wx.CallAfter(self.safe_update, self._system_response_lbl.SetLabel, text[:stop_char])
        self.safe_update_delay(self._system_response_lbl.SetLabel, "")
        self.safe_update_delay(self._system_response_bmp.SetBitmap, self.system_response_good)

    def _user_request_text(self, entities, raw_text):
        for stop_char in range(len(raw_text) + 1):
            time.sleep(0.05)
            wx.CallAfter(self.safe_update, self._user_request_lbl.SetLabel, "%150s" % raw_text[:stop_char])
        self.safe_update_delay(self._user_request_lbl.SetLabel, "")

    def _say_status_update(self, response):
        if "error" in str(response).lower():
            self._error_msg.set()
        elif "unclear" in str(response).lower():
            self._unclear_msg.set()

    def _time_update(self):
        while not self._shutdown.isSet():
            curr_time = datetime.datetime.now()
            time.sleep(1)
            wx.CallAfter(self.safe_update, self._clock_lbl.SetLabel, "%02d:%02d" % (curr_time.hour, curr_time.minute))
            wx.CallAfter(self.safe_update, self._date_lbl.SetLabel, "%02d/%02d/%02d" %
                         (curr_time.day, curr_time.month, curr_time.year % 100))

    def _weather_display(self, description, temp, wind, icon):
        wx.CallAfter(self.safe_update, self.weather_desc_lbl.SetLabel, description)
        wx.CallAfter(self.safe_update, self._weather_temp_lbl.SetLabel, "%02.1fᵒC" % temp)
        wx.CallAfter(self.safe_update, self.weather_wind_lbl.SetLabel, "Wind: %s" % str(wind).replace(' ', '\n'))
        wx.CallAfter(self.safe_update, self._weather_icon.SetBitmap, wx.Bitmap(icon, wx.BITMAP_TYPE_ANY))

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



class GuiPlugin:
    version = '1.0.0.0'
    description = 'GUI'

    def __init__(self):
        threading.Thread(target=self._gui_thread).start()

    def _gui_thread(self):
        gui = wx.PySimpleApp()
        frame = Gui(None, wx.ID_ANY, "")
        gui.SetTopWindow(frame)
        frame.Show()
        t = threading.Thread(target=gui.MainLoop)
        t.setDaemon(1)
        t.start()

