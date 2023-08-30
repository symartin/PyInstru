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

import logging

from ..adapters import VISAAdapter

log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())


class Instrument(object):
    """ This provides the base class for all Instruments, which is
    independent of the particular Adapter used to connect for
    communication to the instrument. It provides basic SCPI commands
    by default, but can be toggled with :code:`includeSCPI`.

    ``adapter`` can be an :class:`Adapter` object used to communicate with the
    instrument, but it can also be a visa address in a form of a ``str`` or a
    GPIB address in the form of an``int``. In both case, the constructor will
    create a :class:`VISAAdapter` object to communicate with the instrument

    :param adapter: An :class:`Adapter` object, a ``str`` ot an ``int``
    :param name: A string name for the instrument
    :param includeSCPI: A boolean, which toggles the inclusion of standard SCPI commands
    """

    # noinspection PyPep8Naming
    def __init__(self, adapter, name, includeSCPI=True, **kwargs):
        try:
            if isinstance(adapter, (int, str)):
                adapter = VISAAdapter(adapter, **kwargs)
        except ImportError:
            raise Exception("Invalid Adapter provided for Instrument since "
                            "PyVISA is not present")

        self.name = name

        self.SCPI = includeSCPI

        self.adapter = adapter
        """ The adapter used to communicate with the Instrument (Visa or other)"""

        self.isShutdown = False
        log.info("Initializing %s." % self.name)

    def id(self):
        """ Requests and returns the identification of the instrument. """
        if self.SCPI:
            return self.adapter.ask("*IDN?").strip()
        else:
            return "Warning: Property not implemented."

    # Wrapper functions for the Adapter object
    def ask(self, command) -> str:
        """ Writes the command to the instrument through the adapter
        and returns the read response.

        :param command: command string to be sent to the instrument
        """
        return self.adapter.ask(command)

    def write(self, command: str):
        """ Writes the command to the instrument through the adapter.

        :param command: command string to be sent to the instrument
        """
        self.adapter.write(command)

    def read(self) -> str:
        """ Reads from the instrument through the adapter and returns the
        response.
        """
        return self.adapter.read()

    def write_raw(self, message: bytes) -> int:
        """Write a byte message to the device.

        :param message: the message to be sent.
        :return: number of bytes written.
        """

        return self.adapter.write_raw(message)

    def values(self, command, **kwargs):
        """ Reads a set of values from the instrument through the adapter,
        passing on any key-word arguments.
        """
        return self.adapter.values(command, **kwargs)

    def clear(self):
        """ Clears the instrument status byte
        """
        self.write("*CLS")

    def reset(self):
        """ Resets the instrument. """
        self.write("*RST")

    def shutdown(self):
        """Brings the instrument to a safe and stable state"""
        self.isShutdown = True
        log.info("Shutting down %s" % self.name)

    def close_adapter(self):
        self.adapter.manager.close()

    def check_errors(self):
        """Return any accumulated errors. Must be reimplemented by subclasses.
        """
        pass
