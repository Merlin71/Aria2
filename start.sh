#!/bin/bash
export LD_LIBRARY_PATH=/usr/local/lib
export PKG_CONFIG_PATH=/usr/local/lib/pkgconfig
python /home/pi/Aria2/Aria.py
killall python
killall pocketsphinx_continuous
