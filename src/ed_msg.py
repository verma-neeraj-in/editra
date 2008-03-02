###############################################################################
# Name: ed_msg.py                                                             #
# Purpose: Provide a messaging/notification system for actions performed in   #
#          the editor.                                                        #
# Author: Cody Precord <cprecord@editra.org>                                  #
# Copyright: (c) 2008 Cody Precord <staff@editra.org>                         #
# License: wxWindows License                                                  #
###############################################################################

"""
FILE: ed_msg.py
AUTHOR: Cody Precord
LANGUAGE: Python
SUMMARY:
    This module provides a light wrapping of a slightly modified pubsub module
to give it a lighter and simpler syntax for usage. It exports three main
methods. The first `PostMessage` which is used to post a message for all
interested listeners. The second `Subscribe` which allows an object to subscribe
its own listener function for a particular message type, all of Editra's core
message types are defined in this module using a naming convention that starts
each identifier with `EDMSG_`. These identifier constants can be used to
identify the message type by comparing them with the value of msg.GetType in a
listener method. The third method is `Unsubscribe` which can be used to remove
a listener from recieving messages.

"""

__author__ = "Cody Precord <cprecord@editra.org>"
__svnid__ = "$Id$"
__revision__ = "$Revision$"

__all__ = ['PostMessage', 'Subscribe', 'Unsubscribe']

#--------------------------------------------------------------------------#
# Dependancies
from extern.pubsub import Publisher

#--------------------------------------------------------------------------#
# Message Type Definitions

#---- General Messages ----#

# Listen to all messages
EDMSG_ALL = ('editra',)

#---- End General Messages ----#

#---- Log Messages ----#
# Used internally by the log system. Listed by priority lowest -> highest
# All message data from these functions are a LogMsg object which is a
# container object for the message string / timestamp / type
#
# Using these message types with the PostMessage method is not suggested for
# use in user code instead use the logging facilities (wx.GetApp().GetLog() or
# util.Getlog() ) as they will handle the formatting that is expected by the 
# log messaging listeners.

# Recieve all log messages (i.e anything put on the logging system)
EDMSG_LOG_ALL = EDMSG_ALL + ('log',)

# Recieve all messages that have been labled (info, events, warnings, errors)
EDMSG_LOG_INFO = EDMSG_LOG_ALL + ('info',)

# Messages generated by ui events
EDMSG_LOG_EVENT = EDMSG_LOG_INFO + ('evt',)

# Recieve only warning messages
EDMSG_LOG_WARN = EDMSG_LOG_INFO + ('warn',)

# Recieve only error messages
EDMSG_LOG_ERROR = EDMSG_LOG_INFO + ('err',)

#---- End Log Messages ----#

#---- File Action Messages ----#

# Recieve notification of all file actions
EDMSG_FILE_ALL = EDMSG_ALL + ('file',)

# File open was just requested / msgdata == file path
EDMSG_FILE_OPENING = EDMSG_FILE_ALL + ('opening',)

# File was just opened / msgdata == file path
EDMSG_FILE_OPENED = EDMSG_FILE_ALL + ('opened',)

# File save requested / msgdata == (filename, filetypeId)
# Note: All listeners of this message are processed *before* the save takes
#       place. Meaning the listeners block the save action until they are
#       finished.
EDMSG_FILE_SAVE = EDMSG_FILE_ALL + ('save',)

# File just written to disk / msgdata == (filename, filetypeId)
EDMSG_FILE_SAVED = EDMSG_FILE_ALL + ('saved',)

#---- End File Action Messages ----#

#---- UI Action Messages ----#

# Recieve notification of all ui typed messages
EDMSG_UI_ALL = EDMSG_ALL + ('ui',)

#- Recieve all Main Notebook Messages
EDMSG_UI_NB = EDMSG_UI_ALL + ('mnotebook',)

# Notebook page changing
# msgdata == (ref to notebook, 
#             index of previous selection,
#             index of current selection)
EDMSG_UI_NB_CHANGING = EDMSG_UI_NB + ('pgchanging',)

# Notebook page changed
# msgdata == (ref to notebook, index of currently selected page)
EDMSG_UI_NB_CHANGED = EDMSG_UI_NB + ('pgchanged',)

# Page is about to close
# msgdata == (ref to notebook, index of page that is closing)
EDMSG_UI_NB_CLOSING = EDMSG_UI_NB + ('pgclosing',)

# Page has just been closed
# msgdata == (ref to notebook, index of page that is now selected)
EDMSG_UI_NB_CLOSED = EDMSG_UI_NB + ('pgclosed',)

## Text Buffer
# msgdata == ((x, y), keycode)
EDMSG_UI_STC_KEYUP = EDMSG_UI_ALL + ('stc', 'keyup')

#---- End UI Action Messages ----#

#---- Misc Messages ----#
EDMSG_THEME_CHANGED = EDMSG_ALL + ('theme',)

#--------------------------------------------------------------------------#
# Public Api

def PostMessage(msgtype, msgdata=None):
    """Post a message containing the msgdata to all listeners that are
    interested in the given msgtype.
    @param msgtype: Message Type EDMSG_*
    @keyword msgdata: Message data to pass to listener (can be anything)

    """
    Publisher().sendMessage(msgtype, msgdata)

def Subscribe(callback, msgtype=EDMSG_ALL):
    """Subscribe your listener function to listen for an action of type msgtype.
    The callback must be a function or a _bound_ method that accepts one
    parameter for the actions message. The message that is sent to the callback
    is a class object that has two attributes, one for the message type and the
    other for the message data. See below example for how these two values can
    be accessed.
    @param callback: Callable function or bound method
    @keyword msgtype: Message to subscribe to (default to all)
    @example:
        def MyCallback(msg):
            print "Msg Type: ", msg.GetType(), "Msg Data: ", msg.GetData()

        class Foo:
            def MyCallbackMeth(self, msg):
                print "Msg Type: ", msg.GetType(), "Msg Data: ", msg.GetData()

        Subscribe(MyCallback, EDMSG_SOMETHING)
        myfoo = Foo()
        Subscribe(myfoo.MyCallBackMeth, EDMSG_SOMETHING)

    """
    Publisher().subscribe(callback, msgtype)

def Unsubscribe(callback, messages=None):
    """Remove a listener so that it doesn't get sent messages for msgtype. If
    msgtype is not specified the listener will be removed for all msgtypes that
    it is associated with.
    @param callback: Function or bound method to remove subscription for
    @keyword messages: EDMSG_* val or list of EDMSG_* vals

    """
    Publisher().unsubscribe(callback, messages)

#-----------------------------------------------------------------------------#
