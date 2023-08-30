#
# This file is part of the PyInstru package,
# parts of the code is based on the  version 0.7.0 of PyMeasure package.
#
# Copyright (c) 2019-2023 Sylvain Martin
# Copyright (c) 2013-2019 PyMeasure Developers
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

import copy
import logging

import pyvisa
from .adapter import Adapter

log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

visa_log = logging.getLogger('pyvisa')
visa_log.addHandler(logging.NullHandler())
visa_log.level = logging.WARNING


# noinspection PyPep8Naming, PyUnresolvedReferences
class VISAAdapter(Adapter):
    """
    Adapter class for the VISA library using PyVISA to communicate
    with instruments.

    :param resource: VISA resource name that identifies the address

    :param visa_library: path of the VISA library or VisaLibrary spec string
    (@py or @ni). if not given, the default for the platform will be used.

    :param kwargs: Any valid keyword arguments for constructing a
    PyVISA instrument: 'access_mode', 'open_timeout', 'resource_pyclass'
    """

    def __init__(self, resourceName, visa_library='', **kwargs):

        if isinstance(resourceName, int):
            resourceName = "GPIB0::%d::INSTR" % resourceName

        super(VISAAdapter, self).__init__()
        self.resource_name = resourceName
        self.manager = pyvisa.ResourceManager(visa_library)

        safeKeywords = ['access_mode', 'open_timeout', 'resource_pyclass',
                        'baud_rate', 'write_termination', 'read_termination']

        kwargsCopy = copy.deepcopy(kwargs)
        for key in kwargsCopy:
            if key not in safeKeywords:
                kwargs.pop(key)

        self.connection = self.manager.open_resource(
            resourceName,
            **kwargs
        )

        # VI_ATTR_TMO_VALUE specifies the minimum timeout value to use
        # (in milliseconds) when accessing the device associated with the
        # given session. By default, 2 000
        self.connection.set_visa_attribute(pyvisa.constants.VI_ATTR_TMO_VALUE, 7500)

    def __repr__(self):
        return "<VISAAdapter(resource='%s')>" % self.connection.resourceName

    def write(self, command: str) -> int:
        """ Writes a command to the instrument

        :param command: SCPI command string to be sent to the instrument
        :return: number of bytes written.
        """
        return self.connection.write(command)

    def write_raw(self, message: bytes) -> int:
        """Write a byte message to the device.

        :param message: the message to be sent.
        :return: number of bytes written.
        """

        return self.connection.write_raw(message)

    def read(self) -> str:
        """ Reads until the buffer is empty and returns the resulting
        ASCII respone

        :returns: String ASCII response of the instrument.
        """
        return self.connection.read()

    def ask(self, command) -> str:
        """ Writes the command to the instrument and returns the resulting
        ASCII response

        :param command: SCPI command string to be sent to the instrument
        :returns: String ASCII response of the instrument
        """
        return self.connection.query(command)
