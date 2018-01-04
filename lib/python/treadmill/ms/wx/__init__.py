"""Treadmill wx extensions.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import datetime
import logging
import os
import sys
import threading
import time

import pkg_resources

# wx import only works on Windows
import wx  # pylint: disable=import-error
from wx.lib.agw import balloontip  # pylint: disable=import-error
from wx.lib.agw import toasterbox  # pylint: disable=import-error

from treadmill import cli
from treadmill import context

_LOGGER = logging.getLogger(__name__)

_TRAY_TOOLTIP = 'Treadmill Ticket Forwarding'


def _spawn_command(name, cmd_clbk, args):
    """Spawn off a command"""
    _LOGGER.debug('cmd_clbk: %r', cmd_clbk)
    _LOGGER.debug('args: %r', args)

    thread = threading.Thread(
        name=name,
        target=cmd_clbk,
        args=args,
    )
    thread.setDaemon(True)
    thread.start()
    return thread


def create_toaster_box(target, title, text, delay):
    """Create a toaster box"""
    toaster = toasterbox.ToasterBox(
        target,
        tbstyle=toasterbox.TB_COMPLEX,
        closingstyle=toasterbox.TB_ONCLICK,
    )

    toaster.SetTitle(title)
    toaster.SetPopupText(text)

    bottomright = wx.Point(
        wx.GetDisplaySize().GetWidth(),
        wx.GetDisplaySize().GetHeight()
    )

    text_len = len(text)
    _LOGGER.debug('text_len: %s', text_len)

    height_perct = .62
    if text_len % 200 < text_len:
        height_perct = .50

    long_text_len = 55

    height = 45
    if text_len > long_text_len:
        height = text_len * height_perct

    _LOGGER.debug('height: %s', height)

    size = wx.Size(280, height)
    pos = wx.Point(
        bottomright.x - size[0] - 2,
        bottomright.y - size[1] - 35,
    )

    toaster.SetPopupSize(size)
    toaster.SetPopupPosition(pos)

    toaster.SetPopupPauseTime(delay)

    tbpanel = toaster.GetToasterBoxWindow()
    panel = wx.Panel(tbpanel, -1)
    sizer = wx.BoxSizer(wx.VERTICAL)

    static_text = wx.StaticText(panel, wx.ID_ANY, text)
    font = wx.Font(8, wx.FONTFAMILY_TELETYPE, wx.NORMAL, wx.FONTWEIGHT_NORMAL)
    static_text.SetFont(font)
    sizer.Add(static_text, 0, wx.ALIGN_LEFT | wx.EXPAND | wx.ALL, 7)

    panel.SetSizer(sizer)
    toaster.AddPanel(panel)

    toaster.Play()


class TicketForwardFrame(wx.Frame):
    """Ticket forwarding window frame"""
    def __init__(self, forward_tickets_clbk, icon=None):
        super(TicketForwardFrame, self).__init__(
            None, -1, _TRAY_TOOLTIP,
            style=(wx.FRAME_NO_TASKBAR | wx.DEFAULT_FRAME_STYLE),
            size=wx.Size(
                wx.GetDisplaySize().GetWidth() - 300,
                wx.GetDisplaySize().GetHeight() - 300,
            ),
        )
        self.forward_tickets_clbk = forward_tickets_clbk
        self.completed_clbk = None
        self.spawned_thread = None

        # An array of the details regarding the last run of the forwarding
        self.details_of_last = []

        # add some buttons and a text control
        panel = wx.Panel(self, -1)
        sizer = wx.BoxSizer(wx.VERTICAL)

        name = 'Forward Tickets'
        button = wx.Button(panel, -1, name)
        button.Bind(wx.EVT_BUTTON, self.on_button)
        sizer.Add(button, 0, wx.ALL, 5)

        self.label = wx.StaticText(panel, label='')
        self.textbox = wx.TextCtrl(
            panel, -1, style=(wx.TE_MULTILINE | wx.TE_READONLY)
        )
        sizer.Add(self.textbox, 1, wx.EXPAND | wx.ALL, 5)

        panel.SetSizer(sizer)

        if icon:
            self.SetIcon(icon)

        self.Bind(wx.EVT_CLOSE, self.on_close)
        self.Bind(wx.EVT_ICONIZE, self.on_iconize)

    def on_button(self, _event):
        """Method called when user clicks button"""
        self.details_of_last = []
        self.textbox.Clear()

        _LOGGER.info('Spawning off new ticket forwarding request from button')
        self.spawned_thread = _spawn_command(
            'button',
            self.forward_tickets_clbk,
            (self.per_cell_clbk, self.completed_clbk,),
        )

    def per_cell_clbk(self, cell, text, state):
        """Per cell callback

        :param str text: text of call output
        :param bool state: state of forwarding execution
        """
        _LOGGER.debug('cell: %s, text: %s, state: %s', cell, text, state)
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        self.details_of_last.append({
            'cell': cell,
            'text': text,
            'state': state,
            'timestamp': timestamp,
        })

        wx.CallAfter(self.textbox.AppendText, text)
        self.Update()

    def on_iconize(self, _event):
        """Called when the "iconize" event is fired"""
        self.Hide()

    def on_close(self, event):
        """Called when the "close" event is fired"""
        self.Hide()
        event.Veto(True)


class TicketForwardTaskBarIcon(wx.TaskBarIcon):
    """Taskbar icon class for Treadmill ticket forwarding"""
    def __init__(self, frame, popup_frame, forward_tickets_clbk,
                 time_interval, icon=None):
        super(TicketForwardTaskBarIcon, self).__init__()

        self.frame = frame
        self.popup_frame = popup_frame

        self.time_interval = time_interval
        self.forward_tickets_clbk = forward_tickets_clbk
        self.completed_clbk = None

        self.timer = None
        self.spawned_thread = None

        self.name = '{}-{}'.format(_TRAY_TOOLTIP, wx.GetUserId())
        self.instance = wx.SingleInstanceChecker(self.name)
        if self.instance.IsAnotherRunning():
            raise Exception('Only one instance allowed')

        if icon:
            self.SetIcon(icon, _TRAY_TOOLTIP)

        self.Bind(wx.EVT_TASKBAR_LEFT_DOWN, self.on_left_down)

    @staticmethod
    def _create_menu_item(menu, label, func):
        """Static method for creating new menu items in sys tray menu"""
        item = wx.MenuItem(menu, -1, label)
        menu.Bind(wx.EVT_MENU, func, id=item.GetId())
        menu.AppendItem(item)
        return item

    def CreatePopupMenu(self):  # pylint: disable=C0103
        """Create popup menu"""
        menu = wx.Menu()
        TicketForwardTaskBarIcon._create_menu_item(
            menu, 'Forward Tickets Now', self.forward_tickets
        )
        menu.AppendSeparator()

        TicketForwardTaskBarIcon._create_menu_item(
            menu, 'Details of Last Forward', self.show_details_of_last_forward,
        )
        menu.AppendSeparator()

        TicketForwardTaskBarIcon._create_menu_item(menu, 'Exit', self.on_exit)
        return menu

    def show_details_of_last_forward(self, _event):
        """Show the details of the last forwarding"""
        text = ''
        delay = 8000

        if not self.popup_frame.details_of_last:
            create_toaster_box(None, '', 'No details of last run yet', delay)

        for detail in self.popup_frame.details_of_last:
            text += '{} - {} @ {}\n'.format(
                detail['cell'],
                ('Success' if detail['state'] else 'Failure'),
                detail['timestamp'],
            )

        create_toaster_box(None, '', text, delay)

    def on_left_down(self, _event):
        """Event called when user clicks the icon in the systray"""
        self.popup_frame.Show()
        self.popup_frame.Raise()
        self.popup_frame.Restore()

    def repeat_ticket_forwarding(self):
        """Repeat for timer"""
        self.forward_tickets(None)

        self.timer = threading.Timer(
            self.time_interval,
            self.repeat_ticket_forwarding,
        )
        self.timer.start()

    def forward_tickets(self, _event):
        """Used to call ticket forwarding from menu item"""
        self.popup_frame.details_of_last = []
        self.popup_frame.textbox.Clear()

        per_cell_clbk = self.popup_frame.per_cell_clbk

        _LOGGER.info('Spawning off a new ticket forwarding request')
        self.spawned_thread = _spawn_command(
            'repeater',
            self.forward_tickets_clbk,
            (per_cell_clbk, self.completed_clbk,)
        )

    def on_exit(self, _event):
        """On exit, cleanup threading"""
        _LOGGER.info('Cancelling timer')
        self.timer.cancel()

        _LOGGER.info('Closing popup frame')
        self.popup_frame.Close()

        _LOGGER.info('Destroying systray icon app')
        wx.CallAfter(self.Destroy)
        _LOGGER.info('Closing systray icon app')
        self.frame.Close()

        sys.exit(0)


class TicketForwardingApp(wx.App):
    """Ticket forwarding wxpython app"""
    def __init__(self, redirect=False, filename=None,
                 forward_tickets_clbk=None, time_interval=None):

        self.forward_tickets_clbk = forward_tickets_clbk
        self.time_interval = time_interval

        super(TicketForwardingApp, self).__init__(
            redirect=redirect, filename=filename,
        )

    def OnInit(self):  # pylint: disable=C0103
        """On app initialization"""
        tray_icon = pkg_resources.resource_stream(
            'treadmill.ms.resources', 'forwarding.ico'
        ).name
        icon = wx.IconFromBitmap(wx.Bitmap(tray_icon))

        frame = wx.Frame(None)
        popup_frame = TicketForwardFrame(
            self.forward_tickets_clbk,
            icon=icon,
        )

        self.SetTopWindow(frame)

        taskbar_icon = TicketForwardTaskBarIcon(
            frame,
            popup_frame,
            self.forward_tickets_clbk,
            self.time_interval,
            icon=icon,
        )

        taskbar_icon.repeat_ticket_forwarding()

        return True


def run_ticket_forward_taskbar(log_filename=None, forward_tickets_clbk=None,
                               time_interval=None):
    """Create a ticket forwarding taskbar"""
    fhandler = logging.FileHandler(log_filename, mode='w')
    formatter = logging.Formatter(
        '%(asctime)s - [%(threadName)s] %(name)s:%(lineno)d %(levelname)s '
        '- %(message)s'
    )
    fhandler.setFormatter(formatter)

    _LOGGER.addHandler(fhandler)

    app = TicketForwardingApp(
        redirect=False,
        forward_tickets_clbk=forward_tickets_clbk,
        time_interval=time_interval,
    )

    app.MainLoop()
