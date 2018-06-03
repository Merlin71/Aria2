## @file
## @brief Zoho email client plugin

import ConfigParser
import logging
import threading
import time
import dateutil.parser
from uuid import uuid4
import socket

from email import parser
import poplib

import keyring
from pydispatch import dispatcher


## @class Weather
## @brief Interaction with openweathermap
## @details Simple weather data retriever from openweather,ap site
class ZohoEmail:
    version = '1.0.0.0'
    description = 'Zoho email client module'

    def __init__(self):
        self.gui_status = str(uuid4())
        self._shutdown = threading.Event()
        self.message_list = dict()
        self.message_list_token = threading.Lock()
        try:
            self._logger = logging.getLogger('moduleEmail')
        except ConfigParser.NoSectionError as e:
            print 'Fatal error  - fail to set logger.Error: %s ' % e.message
            raise ImportError
        self._logger.debug('Email logger started')
        # Reading config file
        try:
            self._config = ConfigParser.SafeConfigParser(allow_no_value=False)
            self._config.read('./configuration/email.conf')
            api_system = self._config.get('API', 'system')
            self.api_user = self._config.get('API', 'user')
            try:
                self.api_key = keyring.get_password(api_system, self.api_user)
            except keyring.errors as e:
                self._logger.warning('Fail to read Zoho token with error: %s. Refer to manual. Module unload' % e)
                raise ImportError
            if self.api_key is None:
                self._logger.warning('Fail to read Zoho token. Refer to manual. Module unload')
                raise ImportError

            self._update_interval = self._config.getint('General', 'update_interval')

            try:
                self._server_url = self._config.get('Server', 'url')
                self._server_port = self._config.getint('Server', 'port')
            except (ConfigParser.Error, ValueError):
                self._server_url = 'pop.zoho.com'
                self._server_port = 995

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

    def _connect(self):
        dispatcher.send(signal='GuiNotification', source=self.gui_status, icon_path="email_refresh.png")
        try:
            pop_conn = poplib.POP3_SSL(self._server_url, self._server_port)

            pop_conn.user("%s@zoho.com" % self.api_user)
            pass_response = pop_conn.pass_(self.api_key)
            if "+OK" in pass_response:
                self._logger.debug('Connected to Email server')
            else:
                self._logger.warning('Fail to connect.Please check password\username. Got response %s' % pass_response)
                return None
        except poplib.error_proto as e:
            dispatcher.send(signal='GuiNotification', source=self.gui_status, icon_path="email_error.png")
            self._logger.warning("Fail to connect.Error %s" % e)
            return None
        except socket.error as e:
            dispatcher.send(signal='GuiNotification', source=self.gui_status, icon_path="email_error.png")
            self._logger.warning("Socket error %s" % e)
            return None
        else:
            self._logger.debug('Pass response %s' % pass_response)
            return pop_conn

    def periodic_update(self):
        time.sleep(15)
        pop_conn = None
        while pop_conn is None:
            pop_conn = self._connect()
            if pop_conn is None:
                self._shutdown.wait(self._update_interval)

        while not self._shutdown.isSet():
            try:
                self._logger.debug('Refreshing email list')
                messages = [pop_conn.retr(i) for i in range(1, len(pop_conn.list()[1]) + 1)]
                messages = ["\n".join(mssg[1]) for mssg in messages]
                messages = [parser.Parser().parsestr(mssg) for mssg in messages]
                new_message = False

                self.message_list_token.acquire()

                for message in messages:
                    if not (message['Message-ID'] in self.message_list):
                        self._logger.info('New message found')
                        self.message_list[str(message['Message-ID'])] = dict(Subject=str(message['Subject']),
                                                                             From=str(message['From']),
                                                                             Time=int(time.mktime(
                                                                                 dateutil.parser.parse(
                                                                                     message['Date']).timetuple())))
                        if time.time() - self.message_list[message['Message-ID']]['Time'] < (1 * 60 * 60):
                            new_message = True

                self.message_list_token.release()

                if new_message:
                    dispatcher.send(signal='GuiNotification', source=self.gui_status, icon_path="new_email.png")
                else:
                    dispatcher.send(signal='GuiNotification', source=self.gui_status, icon_path="")

                for i in range(0, 60 * self._update_interval, 30):
                    self._shutdown.wait(30)
                    self._logger.debug('Sending NOOP')
                    pop_conn.noop()

                    if self._shutdown.isSet():
                        pop_conn.quit()
                        return
            except (socket.error, poplib.error_proto) as e:
                self._logger.warning('Got error - %s. Reconnecting' % e)
                pop_conn = None
                while pop_conn is None:
                    pop_conn = self._connect()
                    if pop_conn is None:
                        self._shutdown.wait(self._update_interval)
                        if self._shutdown.isSet():
                            pop_conn.quit()
                            return

    def user_request(self, entities, raw_text):
        if "mail" in entities and entities['mail'][0]['confidence'] > 0.5:
            dispatcher.send(signal='SpeechAccepted')
            self._logger.debug("Starting email fetch thread")
            try:
                threading.Thread(target=self._user_request, args=(entities,)).start()
            except OSError as e:
                self._logger.warning('Fail to start fetch thread with error %s' % e)

    def _user_request(self, entities):
        if 'contact' in entities:
            if str(entities['contact'][0]['value']) != 'i':
                search_person = str(entities['contact'][0]['value'])
            else:
                search_person = None
        else:
            search_person = None

        if search_person is None:
            # ask for update only
            new_email = 0
            self.message_list_token.acquire()
            for message_id, message_data in self.message_list.iteritems():
                if (time.time() - message_data['Time']) < (1 * 60 * 60):
                    new_email += 1
            if new_email == 0:
                dispatcher.send(signal='SayText', text="You don't have any new email from last hour",
                                callback=self.sythsys_complete)
            else:
                dispatcher.send(signal='SayText', text="You receive %i new email in last hour" % new_email,
                                callback=self.sythsys_complete)
        else:
            new_email = 0
            self.message_list_token.acquire()
            for message_id, message_data in self.message_list.iteritems():
                if ((time.time() - message_data['Time']) < (1 * 60 * 60)) and (search_person in message_data['From']):
                    new_email += 1
            if new_email == 0:
                dispatcher.send(signal='SayText',
                                text="You don't have any new email from %s in last hour" % search_person,
                                callback=self.sythsys_complete)
            else:
                dispatcher.send(signal='SayText', text="You receive %i new email from %s in last hour" %
                                                       (new_email, search_person), callback=self.sythsys_complete)

        self.message_list_token.release()
        dispatcher.send(signal='GuiNotification', source=self.gui_status, icon_path="")

    @staticmethod
    def sythsys_complete():
        dispatcher.send(signal='RestartInteraction')
