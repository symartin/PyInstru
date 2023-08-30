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
from typing import Any

import pyvisa.errors
import numpy as np

from .. import Instrument
from ...tools import load_metadata

log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())


def S_curve_fit(amp: float, min_: float, max_: float, k_: float, a_: float) -> float:
    """
    Calculate the S curve fit value based on the given parameters.
    :returns: float: The S curve fit value.
    """
    return (-1 / k_) * np.log((((max_ - min_) / (amp - min_)) ** (1 / a_)) - 1)


class DrVe10Mo(Instrument):
    """
    Represents the DR-VE-10-MO amplifier.
    """
    flag = 0

    def __init__(self, adapter, **kwargs):

        super().__init__(adapter, "DR-VE-10-MO",
                         baud_rate=115200,
                         write_termination='\r',
                         read_termination='\r',
                         **kwargs)

    def write(self, cmd):

        try:
            res = self.ask(cmd)
            if res.strip() == "ERR":
                if self.flag < 10:
                    print(cmd, 'ERR')
                    self.flag += 1
                    self.write(cmd)
                else:
                    raise IOError("%s return an error" % cmd)
        except pyvisa.errors.VisaIOError as e:
            log.info("Encountered Visa IO Error. Trying Again.")

    def set_settings(self, gain: float, amplitude: float, crosspoint: float, **kwarg):
        self.set_gain(gain)
        self.set_amplitude(amplitude)
        self.set_crosspoint(crosspoint)

    def set_gain(self, gain):
        """ set the gain in percentage """
        if not( 0 <= gain <= 100):
            raise ValueError("Gain outside 0-100% range")
        gain *= 10
        self.flag = 0
        self.write('GD %d' % gain)

    def gain(self) -> float:
        """ return the gain in percentage """
        return int(self.ask("GD?")) / 10

    def set_amplitude(self, amplitude):
        """ set the amplitude in percentage """
        if not( 0 <= amplitude <= 100):
            raise ValueError("Amplitude outside 0-100% range")
        amplitude *= 10

        self.flag = 0
        self.write('AM %d' % amplitude)

    def amplitude(self) -> float:
        """ return the amplitude in percentage """

        return int(self.ask("AM?")) / 10

    def set_crosspoint(self, crosspoint):
        """ set the cross point in percentage """
        if not (0 <= crosspoint <= 100):
            raise ValueError("Cross-point outside 0-100% range")
        crosspoint *= 10

        self.flag = 0
        self.write('XP %d' % crosspoint)

    def crosspoint(self) -> float:
        """ return the cross-point in percentage """

        return int(self.ask("XP?")) / 10

    def temperature(self) -> int:
        return int(self.ask("T?"))

    def enable(self):
        """ enable the amplifier """

        self.flag = 0
        self.write("P ON")

    def disable(self):
        """ disable the amplifier """

        self.flag = 0
        self.write("P OFF")

    def shutdown(self) -> None:
        """
        Ensures that the current or voltage is turned to zero
        and disables the output.
        """
        self.disable()

        self.isShutdown = True
        log.info("Shutting down %s.", self.name)

    @staticmethod
    def load_calibration(calibration_file: str) -> dict[str, Any]:
        """
        Read amplifier calibration files and initialize parameters.
        """
        params = load_metadata(calibration_file)
        fit = dict(params['fit'])
        calib_params = dict(params['amplifier settings'])
        calib_params['fit'] = fit
        return calib_params

    @classmethod
    def define_input_amplitude(cls, amplitude, calib_dict: dict[str, Any]) -> float:
        coeffs = calib_dict['fit']['coefficients']

        return S_curve_fit(amplitude, *coeffs)
