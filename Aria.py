#!/usr/bin/python
## @file
## @brief Main file

import ConfigParser
import atexit
import inspect
import logging
import logging.config
import os
import sys
from time import sleep
import threading

import pydevd
from pydispatch import dispatcher


@atexit.register
## @fn def clean_exit():
## @brief Cleanup function
## @details Close all debug/log session and perform clean exit
def clean_exit():
    print 'Main thread termination'
    try:
        if pydevd.GetGlobalDebugger() is not None:
            print '#################################################'
            print '########   Remote debug session ended  ##########'
            print '#################################################'
            pydevd.stoptrace()
    except:
        pass


## @fn def aria_start():
## @brief  Startup function
## @details Start all services and load runners
## @note Load logger configuration, and run settings
## @see https://docs.python.org/2/library/logging.html
def aria_start():
    # Start reading _config file
    _config = ConfigParser.SafeConfigParser(allow_no_value=True)
    _config.read('./configuration/main.conf')
    # Setting up debug session
    try:
        # Parse configuration options
        if _config.getboolean('Debug', 'Debug'):
            print 'Trying to start debug session.'
            _debug_host = _config.get('Debug', 'host').strip()
            _debug_port = _config.getint('Debug', 'port')
            print 'Remote host - %s  on port %i' % (_debug_host, _debug_port)
            pydevd.settrace(_debug_host, port=_debug_port, stdoutToServer=True, stderrToServer=True, suspend=False)
            print '#################################################'
            print '########  Remote debug session started ##########'
            print '#################################################'
        else:
            print 'Start in normal mode.'
    except ConfigParser.NoSectionError:
        print 'No debug section found.Starting in normal mode'
        print 'Missing debug parameters.Please refer manual.Starting in normal mode'
    # setting up logger
    try:
        logging.config.fileConfig('main.logger')
        _logger = logging.getLogger('root')
    except ConfigParser.NoSectionError as e:
        print 'Fatal error  - fail to set _logger.Error: %s ' % e.message
        exit(-1)
    _logger.debug('Logger started')
    # Loading modules
    # Storing loaded modules
    active_modules = list()
    try:
        # Search all files in plugin folder
        plugin_dir = _config.get('Modules', 'Path').strip()
        _logger.info('Searching modules in: %s' % plugin_dir)
    except IOError:
        # Incorrect folder - Switching to default
        _logger.info('Error getting plugin dir using default - plugins')
        plugin_dir = 'plugins'
    try:
        # Create list of disables modules and classes
        disable_modules = _config.get('Modules', 'Disabled')
        disable_modules = disable_modules.strip().split(',')
        disable_classes = _config.get('Classes', 'Disabled')
        disable_classes = disable_classes.strip().split(',')
    except ConfigParser as e:
        _logger.fatal('Fail to read config file with error %s' % e)
        exit(-1)
    _logger.info('Disabled modules : %s' % disable_modules)
    _logger.info('Disabled classes : %s' % disable_classes)

    if not os.path.exists(plugin_dir):
        _logger.critical('Plugins folder not exist')
        exit(-1)
    # Searching .py files in folder 'plugins'
    for fname in os.listdir(plugin_dir):
        # Look only for py files
        if (fname.endswith('.py')) and ('plugin' in fname.lower()):
            # Cut .py from path
            module_name = fname[: -3]
            # Skip base,__init__  and disabled files
            if module_name != 'base' and module_name != '__init__' and not (module_name in disable_modules):
                _logger.info('Found module %s' % module_name)
                # Load module and add it to list of loaded modules
                package_obj = __import__(plugin_dir + '.' + module_name)
                active_modules.append(module_name)
            else:
                _logger.info('Skipping %s' % fname)

    # Retrieving modules
    _loaded_modules = []
    for modulename in active_modules:
        module_obj = getattr(package_obj, modulename)
        # Looking for classes in file
        for elem in dir(module_obj):
            obj = getattr(module_obj, elem)
            # If this a class ?
            if inspect.isclass(obj):
                if elem in disable_classes:
                    _logger.info('Skipping %s' % obj)
                    continue
                # Creating object
                try:
                    _logger.info('Loading module %s from %s' % (elem, modulename))
                    try:
                        _module = obj()
                    except (ImportError, TypeError) as e:
                        # Some error while creating module instance
                        _logger.fatal('Incorrect module. Error %s' % e)
                except ImportWarning:
                    _logger.warning('Failed to load %s from %s' % (elem, modulename))
                    del _module
                    pass
                else:
                    # Store module instance
                    _loaded_modules.append(_module)
                    _logger.info('Module %s (version: %s) loaded' % (elem, _module.version))
    sleep(5)  # Init time
    _logger.info('All modules loaded')
    # Create event for shutdown of main thread
    dispatcher.connect(emergency_shutdown, signal='EmergencyShutdown')
    dispatcher.send(signal='SayResponse', response='Welcome')
    try:
        while True:
            #  We will wait here until shutdown
            sleep(1)
            if shutdown_flag.isSet():
                break
    except KeyboardInterrupt:
        _logger.warning("Keyboard Interrupt received")
    except SystemExit:
        _logger.warning("System shutdown")

    for _module in _loaded_modules:
        try:
            _logger.info('Unloading module %s' % _module)
            # Calling destructor will unload module
            del _module
        except:
            # Ignore all error while shutdown
            _logger.warning('Fail to unload module %s' % _module)
    _logger.info("All module unloaded")


def emergency_shutdown():
    # Callback function of "EmergencyShutdown" event
    shutdown_flag.set()


if __name__ == '__main__':
    # Shutdown flag
    shutdown_flag = threading.Event()
    # Start main function
    aria_start()
