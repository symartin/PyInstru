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


class Adapter(object):
    """ Base class for Adapter child classes, which adapt between the Instrument 
    object and the connection, to allow flexible use of different connection 
    techniques.

    This class should only be inherited from.
    """

    def write(self, command):
        """ Writes a command to the instrument

        :param command: SCPI command string to be sent to the instrument
        """
        raise NameError("Adapter (sub)class has not implemented writing")

    def ask(self, command):
        """ Writes the command to the instrument and returns the resulting 
        ASCII response

        :param command: SCPI command string to be sent to the instrument
        :returns: String ASCII response of the instrument
        """
        self.write(command)
        return self.read()

    def read(self):
        """ Reads until the buffer is empty and returns the resulting
        ASCII respone

        :returns: String ASCII response of the instrument.
        """
        raise NameError("Adapter (sub)class has not implemented reading")

    def values(self, command, separator=',', cast=float):
        """ Writes a command to the instrument and returns a list of formatted
        values from the result

        :param command: SCPI command to be sent to the instrument
        :param separator: A separator character to split the string into a list
        :param cast: A type to cast the result
        :returns: A list of the desired type, or strings where the casting fails
        """
        results = str(self.ask(command)).strip()
        results = results.split(separator)
        for i, result in enumerate(results):
            try:
                if cast == bool:
                    # Need to cast to float first since results are usually
                    # strings and bool of a non-empty string is always True
                    results[i] = bool(float(result))
                else:
                    results[i] = cast(result)
            except Exception:
                pass  # Keep as string
        return results