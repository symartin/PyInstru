#
# This file is part of the PyInstru package,
#
# Copyright (c) 2019-2023 Sylvain Martin
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#

import logging
from typing import Optional
import clr
clr.AddReference('C:\Windows\SysWOW64\mcl_RF_Switch_Controller_NET45.dll')
from mcl_RF_Switch_Controller_NET45 import USB_RF_SwitchBox

from ...adapters import Adapter
from .. import Instrument

# Setup logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())


class RFSwitchBoxUSB(Instrument):
    """
    Represents the MiniCircuit RF switch box connected trough USB and
    provides a high-level interface for interacting with the instrument.
    """

    def __init__(self, serial: str = None, channel='A'):
        """
        Init the object. This instrument does not need an adapters.

        :param serial: Optional. The serial number of the USB switch matrix.
        Can be omitted if only one switch matrix.
        """
        super(RFSwitchBoxUSB, self).__init__(
            Adapter(), "MiniCircuit RF USB switch box ", includeSCPI=False,
        )

        self.channel = channel

        # connect to the COM DLL
        self.dll_switch = USB_RF_SwitchBox()
        self.connect(serial)

    def connect(self, serial: str = None):
        """
        Initializes the USB connection to a switch matrix. If multiple switch
        matrices are connected to the same computer, then the serial number
        should be included, otherwise this can be omitted. The switch should be
        disconnected on completion of the program using the disconnect function.

        :param serial: Optional. The serial number of the USB switch matrix.
        Can be omitted if only one switch matrix.

        :return: None
        """
        log.info("Connecting to the RF switch %s" % serial)

        if serial is not None:
            self.dll_switch.Connect(serial)
        else:
            self.dll_switch.Connect()

    def set_switch(self, value: int, channel: Optional[str] = None) -> None:
        """
        This function sets an individual SPDT within the switch matrix while
        leaving any other switches unchanged. The switches are designated A to D,
        as labeled on the front of the switch matrix (not all switches are
        available on all models)

        :param value: 0 Connect Com port to port 1, 1 Connect Com port to port 2
        :param channel: the channel : A, B, C or D
        :return:
        """
        if channel is None:
            channel = self.channel

        if value or value >= 1:
            error = self.dll_switch.Set_Switch(channel.capitalize(), 1)
        else:
            error = self.dll_switch.Set_Switch(channel.capitalize(), 0)

        if error == 0:
            raise EnvironmentError("RF switch : Command failed")
        elif error == 2:
            raise EnvironmentError(
                "RF switch : Command failed (communication successful but 24V "
                "DC supply is disconnected)")

    def switch(self, channel: Optional[str] = None) -> None:
        """
        Returns the states of all switches in the switch matrix.
        :param channel: the channel : A, B, C or D
        :return: 0 or 1
        """
        channel_dict = {'A': 0, 'B': 1, 'C': 2, 'D': 3}
        StatusRet = self.dll_switch.GetSwitchesStatus()

        if channel is None:
            channel = self.channel

        if channel.capitalize() in channel_dict.keys():
            return StatusRet >> channel_dict[channel.capitalize()] & 1

    @property
    def connection_status(self) -> bool:
        """
        This function checks whether there is an open software connection to the
        switch matrix. This will be true if the connect function (or similar)
        has previously been called
        :return: true if connected
        """
        return self.dll_switch.GetConnectionStatus() == 1

    def clear(self):
        """ Do nothing. """
        pass

    def reset(self):
        """ Do nothing. """
        pass

    def shutdown(self, close_adapter: bool = True):
        """Brings the instrument to a safe and stable state"""
        self.isShutdown = True
        self.disconnect()
        log.info("Shutting down %s" % self.name)

    def check_errors(self):
        """Do nothing."""
        pass

    def disconnect(self) -> None:
        """
        This function is called to close the connection to the switch matrix
        after completion of the switching routine. It is strongly recommended
        that this function is used prior to ending the program. Failure to do
        so may result in a connection problem with the device. Should this occur,
        shut down the program and unplug the switch matrix from the computer,
        then reconnect the switch matrix before attempting to start again.
        """
        self.dll_switch.Disconnect()
