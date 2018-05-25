## @file
## @brief Weather plugin
import ConfigParser
import logging
import json
import os
import threading
import urllib
import time
from bisect import bisect_left
import dateutil.parser
from uuid import uuid4

import keyring
from pydispatch import dispatcher


## @class Weather
## @brief Interaction with openweathermap
## @details Simple weather data retriever from openweather,ap site
class Weather:
    version = '1.0.0.0'
    description = 'Weather module'

    def __init__(self):
        self._shutdown = threading.Event()
        self.weather_data = []
        self.gui_status = str(uuid4())
        try:
            self._logger = logging.getLogger('moduleWeather')
        except ConfigParser.NoSectionError as e:
            print 'Fatal error  - fail to set logger.Error: %s ' % e.message
            raise ImportError
        self._logger.debug('Weather logger started')
        # Reading config file
        try:
            self._config = ConfigParser.SafeConfigParser(allow_no_value=False)
            self._config.read('./configuration/weather.conf')
            api_system = self._config.get('API', 'system')
            api_user = self._config.get('API', 'user')
            try:
                self.api_key = keyring.get_password(api_system, api_user)
            except keyring.errors as e:
                self._logger.warning('Fail to read OpenWeather token with error: %s. Refer to manual. Module unload' % e)
                raise ImportError
            if self.api_key is None:
                self._logger.warning('Fail to read OpenWeather token. Refer to manual. Module unload')
                raise ImportError
            self._main_city = self._config.get('General', 'base_city')
            self._update_interval = self._config.getint('General', 'update_interval')

            try:
                self._base_url = self._config.get('General', 'base_url')
            except ConfigParser.Error:
                self._base_url = None

            try:
                self._icon_url = self._config.get('General', 'icon_url')
            except ConfigParser.Error:
                self._icon_url = None

            self._temp_folder = self._config.get('General', 'temp_folder')
            self._units = self._config.get('General', 'units')
            self._dump_json = self._config.getboolean('Debug', 'save_json')
            if not os.path.exists(self._temp_folder):
                try:
                    os.makedirs(self._temp_folder)
                except IOError as e:
                    self._logger.error('Fail to temporary folder with error %s.Module unload' % e)
                    raise ImportError
        except ConfigParser.Error as e:
            self._logger.error('Fail to read configuration file with error %s.Module unload' % e)
            raise ImportError

        try:
            # register on user input
            dispatcher.connect(self.user_request, signal='SpeechRecognize', sender=dispatcher.Any)
        except dispatcher.DispatcherTypeError as e:
            self._logger.error('Fail to subscribe on "SpeechRecognize" event with error %s.Module unload' % e)
            raise ImportError

        self._logger.debug("Starting periodic update thread")
        try:
            threading.Thread(target=self.periodic_update).start()
        except OSError as e:
            self._logger.warning('Fail to start periodic update thread with error %s' % e)

        self._logger.info('Weather module ready')

    def __del__(self):
        self._shutdown.set()
        self._logger.info('Weather module shutdown')

    def periodic_update(self):
        self._logger.debug("Periodic update start started")
        weather_data = WeatherData(self.api_key, self._logger)
        weather_data.auto_update = False
        weather_data.units = self._units
        weather_data.icon_folder = self._temp_folder
        weather_data.city_name = self._main_city
        time.sleep(15)
        while True:
            self._logger.debug("Requesting periodic update for city %s" % weather_data.city_name)
            dispatcher.send(signal='GuiNotification', source=self.gui_status, icon_path="weather_none.png")
            weather_data.update()
            dispatcher.send(signal='GuiNotification', source=self.gui_status, icon_path="")
            dispatcher.send(signal='WeatherUpdate',
                            description=weather_data.short_description,
                            temp=weather_data.temp,
                            wind=weather_data.wind_description,
                            icon=weather_data.icon
                            )
            self._shutdown.wait(self._update_interval * 60 * 60)
            if self._shutdown.isSet():
                self._logger.debug("Shutdown flag set  - exit from update thread")
                return

    def user_request(self, entities, raw_text):
        if "weather" in entities and entities['weather'][0]['confidence'] > 0.5:
            dispatcher.send(signal='SpeechAccepted')
            self._logger.debug("Starting weather fetch thread")
            try:
                threading.Thread(target=self._user_request, args=(entities, )).start()
            except OSError as e:
                self._logger.warning('Fail to start fetch thread with error %s' % e)

    def _user_request(self, entities):
        # if specific city requested
        if 'location' in entities and entities['location'][0]['confidence'] > 0.5:
            self._logger.debug('Selected city')
            city = str(entities['location'][0]['value'])
        else:
            self._logger.debug('Using default city')
            city = self._main_city

        # time
        if 'datetime' in entities and entities['datetime'][0]['confidence'] > 0.5:
            unix_time = time.mktime(dateutil.parser.parse(str(entities['datetime'][0]['value'])).timetuple())
            self._logger.debug('Time requested - %i' % unix_time)
        else:
            unix_time = time.time()
            self._logger.debug('Using current time - %i' % unix_time)

        weather_data = WeatherData(self.api_key, self._logger)
        weather_data.auto_update = False
        weather_data.units = self._units
        weather_data.icon_folder = self._temp_folder
        weather_data.city_name = city
        weather_data.request_time = unix_time
        dispatcher.send(signal='GuiNotification', source=self.gui_status, icon_path="weather_none.png")
        try:
            weather_data.update()
        except IOError:
            dispatcher.send(signal='SayText', text="Sorry, can't receive weather data")
        else:
            if entities['weather'][0]['value'] in ['rain', 'umbrella']:
                if weather_data.rain is not None:
                    response = "Yes, it look like. " + weather_data.description
                else:
                    response = "No, it not look like." + weather_data.description
            elif entities['weather'][0]['value'] in ['show', 'blizzard']:
                if weather_data.show is not None:
                    response = "Yes, it look like. " + weather_data.description
                else:
                    response = "No, it not look like." + weather_data.description
            else:
                response = weather_data.description

            dispatcher.send(signal='SayText', text=response, callback=self.sythsys_complete)
        finally:
            dispatcher.send(signal='GuiNotification', source=self.gui_status, icon_path="")

    @staticmethod
    def sythsys_complete():
        dispatcher.send(signal='RestartInteraction')


class WeatherData(object):
    def __init__(self, api_key, logger):
        self._api_key = api_key
        self._logger = logger
        self._auto_update = False
        self._city_name = None
        self._requested_time = None
        self._units = None

        self.weather_data = dict(
                title=None,
                description=None,
                icon=None,
                temp=None,
                temp_max=None,
                temp_min=None,
                pressure=None,
                humidity=None,
                wind_speed=None,
                wind_direction=None,
                rain=None,
                snow=None,
                clouds=None,
                timestamp=None
            )
        self._base_url = "http://api.openweathermap.org/data/2.5/"
        self._icon_url = "http://openweathermap.org/img/w/"
        self._icon_folder = ""

    def update(self):
        if self._city_name is None:
            return
        # construct url
        if (self._requested_time is None) or (abs(time .time() - self._requested_time) < 3 * 60 * 60):
            # request current weather
            request_url = self._base_url + "find?q=%s" % self._city_name
            forecast = False
        else:
            # request forecast weather
            request_url = self._base_url + "forecast?q=%s" % self._city_name
            forecast = True
        if self._units is not None:
            request_url = request_url + "&units=%s" % self._units
        request_url = request_url + "&appid=%s" % self._api_key
        # download
        try:
            self._logger.debug("Requesting json. Forecast mode - %s" % forecast)
            response_json = urllib.urlopen(request_url)
        except IOError as e:
            raise IOError('Fail to download JSON with error %s' % e)

        weather_json = json.loads(response_json.read())
        # Parse
        if str(weather_json['cod']) != "200":
            raise IOError("Fail to retrieve json with error code %s - request string %s" % (str(weather_json['cod']),
                                                                                            request_url))
        else:
            self._logger.debug("Weather data receive")
        if forecast:
            forecast_time = []
            for single_forecast in weather_json['list']:
                # collect all forecast times
                forecast_time.append(single_forecast['dt'])

            pos = bisect_left(forecast_time, self._requested_time)
            if pos == 0:
                index = 0
            elif pos == len(forecast_time):
                index = len(forecast_time) - 1
            else:
                before = forecast_time[pos - 1]
                after = forecast_time[pos]
                if after - self._requested_time < self._requested_time - before:
                    index = pos
                else:
                    index = pos - 1

            self.weather_data = dict(
                title=str(weather_json['list'][index]['weather'][0]['main']),
                description=str(weather_json['list'][index]['weather'][0]['description']),
                icon=str(weather_json['list'][index]['weather'][0]['icon']),
                temp=weather_json['list'][index]['main']['temp'],
                temp_max=weather_json['list'][index]['main'].get('temp_max', None),
                temp_min=weather_json['list'][index]['main'].get('temp_min', None),
                pressure=weather_json['list'][index]['main']['pressure'],
                humidity=weather_json['list'][index]['main']['humidity'],
                wind_speed=weather_json['list'][index]['wind'].get('speed', None),
                wind_direction=weather_json['list'][index]['wind'].get('deg', None),
                rain=None,
                snow=None,
                clouds=weather_json['list'][index]['clouds'].get('all', None),
                timestamp=int(weather_json['list'][index]['dt'])
            )
            self._city_name = weather_json['city']['name']
        else:
            index = 0
            self.weather_data = dict(
                title=str(weather_json['list'][index]['weather'][0]['main']),
                description=str(weather_json['list'][index]['weather'][0]['description']),
                icon=str(weather_json['list'][index]['weather'][0]['icon']),
                temp=weather_json['list'][index]['main']['temp'],
                temp_max=weather_json['list'][index]['main'].get('temp_max', None),
                temp_min=weather_json['list'][index]['main'].get('temp_min', None),
                pressure=weather_json['list'][index]['main']['pressure'],
                humidity=weather_json['list'][index]['main']['humidity'],
                wind_speed=weather_json['list'][index]['wind'].get('speed', None),
                wind_direction=weather_json['list'][index]['wind'].get('deg', None),
                rain=weather_json['list'][index].get('rain', None),
                snow=weather_json['list'][index].get('show', None),
                clouds=weather_json['list'][index]['clouds'].get('all', None),
                timestamp=int(weather_json['list'][index]['dt'])
            )
            self._city_name = weather_json['list'][0]['name']

        if os.path.isdir(self.icon_folder):
            try:
                urllib.urlretrieve(self.icon_url + self.weather_data['icon'] + ".png",
                                   os.path.join(self.icon_folder, self.weather_data['icon'] + ".png"))
            except IOError:
                self._logger.warning('Fail to download icon')
            else:
                self.weather_data['icon'] = os.path.join(self.icon_folder, self.weather_data['icon'] + ".png")


    @property
    def base_url(self):
        return self._base_url

    @base_url.setter
    def base_url(self, url):
        self._logger.warning('Changing base url - %s' % url)
        self._base_url = url

    @property
    def icon_url(self):
        return self._icon_url

    @icon_url.setter
    def icon_url(self, url):
        self._logger.warning('Changing icon url - %s' % url)
        self._icon_url = url

    @property
    def icon_folder(self):
        return self._icon_folder

    @icon_folder.setter
    def icon_folder(self, folder):
        if os.path.isdir(folder):
            self._logger.debug("Changing icon folder - %s" % folder)
            self._icon_folder = folder
        else:
            raise ValueError("Incorrect folder")

    @property
    def icon(self):
        return self.weather_data['icon']

    @property
    def city_name(self):
        return self._city_name

    @city_name.setter
    def city_name(self, name):
        self._city_name = name
        self._logger.debug("City updated - %s" % name)
        if self._auto_update:
                self.update()

    @property
    def auto_update(self):
        return self._auto_update

    @auto_update.setter
    def auto_update(self, state):
        self._auto_update = state
        self._logger.debug("Auto update active- %s" % state)

    @property
    def request_time(self):
        return self._requested_time

    @request_time.setter
    def request_time(self, req_time):
        self._requested_time = req_time
        self._logger.debug("Request time updated - %i" % req_time)
        if self._city_name is not None:
            if self._auto_update:
                self.update()

    @property
    def units(self):
        if self._units is None:
            return 'metric'
        else:
            return self._units

    @units.setter
    def units(self, unit):
        if unit not in ['metric', 'imperial']:
            raise AttributeError("Incorrect units")
        else:
            self._units = unit
            self._logger.debug("Change units - %s" % unit)

    @property
    def temp(self):
        return self.weather_data['temp']

    @property
    def temp_max(self):
        return self.weather_data['temp_max']

    @property
    def temp_min(self):
        return self.weather_data['temp_min']

    @property
    def pressure(self):
        return self.weather_data['pressure']

    @property
    def humidity(self):
        return self.weather_data['humidity']

    @property
    def wind_speed(self):
        return self.weather_data['wind_speed']

    @property
    def wind_direction(self):
        return self.weather_data['wind_direction']

    @property
    def rain(self):
        return self.weather_data['rain']

    @property
    def show(self):
        return self.weather_data['snow']

    @property
    def clouds(self):
        return self.weather_data['clouds']

    @property
    def measure_time(self):
        return self.weather_data['timestamp']

    @property
    def title(self):
        return self.weather_data['title']

    @property
    def short_description(self):
        return self.weather_data['description']

    @property
    def wind_description(self):
        description = ""
        wind_direction = {0: 'northerly', 45: 'northeasterly', 90: 'easterly', 135: 'southeasterly',
                          180: 'southerly', 225: 'southwesterly', 270: 'westerly', 315: 'Northwesterly'}
        
        if self.wind_direction is not None:
            wind_direction_description = wind_direction[min(wind_direction, key=lambda x: abs(x - self.wind_direction))]

            if self.wind_speed is not None:
                if self.units == 'metric':
                    if self.wind_speed < 0.3:
                        description = "without wind"
                    elif self.wind_speed < 1.5:
                        description = "%s light wind" % wind_direction_description
                    elif self.wind_speed < 3.3:
                        description = "%s light breeze" % wind_direction_description
                    elif self.wind_speed < 5.5:
                        description = "%s gentle breeze" % wind_direction_description
                    elif self.wind_speed < 7.9:
                        description = "%s moderate breeze" % wind_direction_description
                    elif self.wind_speed < 10.7:
                        description = "%s fresh breeze" % wind_direction_description
                    elif self.wind_speed < 13.8:
                        description = "%s strong breeze" % wind_direction_description
                    elif self.wind_speed < 17.1:
                        description = "%s high wind" % wind_direction_description
                    elif self.wind_speed < 20.7:
                        description = "%s Gale" % wind_direction_description
                    elif self.wind_speed < 24.4:
                        description = "%s strong gale" % wind_direction_description
                    elif self.wind_speed < 28.4:
                        description = "%s storm" % wind_direction_description
                    elif self.wind_speed < 32.6:
                        description = "violent storm"
                    else:
                        description = "hurricane"
                else:
                    if self.wind_speed < 1:
                        description = "without wind"
                    elif self.wind_speed < 3:
                        description = "%s light wind" % wind_direction_description
                    elif self.wind_speed < 7:
                        description = "%s light breeze" % wind_direction_description
                    elif self.wind_speed < 12:
                        description = "%s gentle breeze" % wind_direction_description
                    elif self.wind_speed < 18:
                        description = "%s moderate breeze" % wind_direction_description
                    elif self.wind_speed < 24:
                        description = "%s fresh breeze" % wind_direction_description
                    elif self.wind_speed < 31:
                        description = "%s strong breeze" % wind_direction_description
                    elif self.wind_speed < 38:
                        description = "%s high wind" % wind_direction_description
                    elif self.wind_speed < 46:
                        description = "%s Gale" % wind_direction_description
                    elif self.wind_speed < 54:
                        description = "%s strong gale" % wind_direction_description
                    elif self.wind_speed < 63:
                        description = "%s storm" % wind_direction_description
                    elif self.wind_speed < 70:
                        description = "violent storm"
                    else:
                        description = "hurricane"

        return description

    @property
    def description(self):
        desc = "Weather in %s is %s with temperature %3.1f " % (self.city_name, self.title, self.temp)
        wind = self.wind_description
        if "without" not in wind:
            desc = desc + " with %s" % wind
        return desc









