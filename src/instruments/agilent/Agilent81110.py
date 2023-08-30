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
from typing import Final, Literal, Tuple

from .. import Instrument

import logging
import time

__all__ = ['Agilent81110', 'TriggerSourceType']

log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

TriggerSourceType: Final = Literal['external', 'manual', 'immediate', 'internal']

MILLI = 10 ** -3
MICRO = 10 ** -6
NANO = 10 ** -9


class Agilent81110(Instrument):
    """ Represents the Agilent 81110 Pulse Generator and provides a high-level
    interface for interacting with the instrument."""

    POLARITIES = {'positive': 'NORM', 'negative': 'INV'}
    UNIT = {'s': 's', 'ms': 'ms', 'us': 'us', 'ns': 'ns'}
    PULSE_MODE = {'double': 'ON', 'single': 'OFF'}
    TRIGGER_MODE = {'gated': 'LEV', 'single': 'EDGE', 'continuous': 'continuous'}

    CHANNEL_NUMBER: Final[int] = 2
    """ The number of channels available """

    MINIMUM_AMPLITUDE: Final[float] = 100 * MILLI
    """ The minimum pulse amplitude (in voltage) the PG can send """

    MINIMUM_PULSEWIDTH: Final[float] = 3.1 * NANO
    """ The minimum pulse width (in second) the PG can send """

    def __init__(self, adapter, **kwargs):
        super(Agilent81110, self).__init__(adapter, "Agilent 81110 Pulse Generator", **kwargs)

    @staticmethod
    def _is_off_str(str_or_bool):
        if str(str_or_bool).strip().capitalize() == 'OFF' \
                or (type(str_or_bool) is bool and str_or_bool is False) \
                or (type(str_or_bool) is int and str_or_bool == 0):
            return 'OFF'
        else:
            return 'ON'

    def set_output(self, on_off=False, channel=1):
        """
        This command enables or disables a channel of the pulse generator.

        :param on_off: boolean True : enable, False : disables
        :param channel: the output channel int from 1 to 2
        :return: None
        """
        self.write("OUTP%d:STAT %s;" % (channel, self._is_off_str(on_off)))

    def enable(self, channel=1):
        """"
        This command enables a channel of the pulse generator output.

        :param channel: the output channel int from 1 to 2
        :return: None
        """
        self.write("OUTP%d:STAT ON" % channel)

    def disables(self, channel=1):
        """"
        This command disables a channel of the pulse generator output.

        :param channel: the output channel int from 1 to 2
        :return: None
        """
        self.write("OUTP%d:STAT OFF" % channel)

    def output(self, channel=1):
        """
        returns the output state of the  channel :code:channel

        :param channel:the output channel int from 1 to 2
        :return: boolean True: enable, False: disables
        """
        return int(self.ask("OUTP%d:STAT?" % channel)) > 0

    ############################################################################
    #                           output configuration                           #
    ############################################################################
    def load_compensation(self, channel=1):
        """
        This command query the automatic calculation of the load impedance for
        the selected output channel.

        Not Implemented on Agilent 81110

        :param channel: the output channel int from 1 to 2
        :return: return False if the automatic load compensation is OFF, True otherwise
        """
        raise NotImplemented("Not Implemented on Agilent 81110")

    def set_load_compensation(self, on_off=False, channel=1):
        """
        This command set the automatic calculation of the load impedance
        for the selected output channel.

        Not Implemented on Agilent 81110

        :param on_off: boolean True : ON, False: OFF
        :param channel: the output channel int from 1 to 2
        :return: None
        """
        raise NotImplemented("Not Implemented on Agilent 81110")

    def load_impedance(self, channel=1):
        """
        This command queries the load impedance value for the selected
        output channel

        Use this command to query the expected load impedance of the device
        under-test at the OUTPUT connectors. If you have a non-50 Ω load,
        the output levels at the device-under-test will not be the levels
        you program or set via the front panel unless you set the expected
        load using this command.

        :param channel: the output channel int from 1 to 2
        :return: the load impedance in Ohms
        """
        return float(self.ask(":OUTP%d:IMP:EXT?" % channel))

    def set_load_impedance(self, impedance=50, channel=1):
        """
        This command sets the load impedance value for the selected
        output channel.

        Use this command to set the expected load impedance of the device
        under-test at the OUTPUT connectors. If you have a non-50 Ω load,
        the output levels at the device-under-test will not be the levels
        you program or set via the front panel unless you set the expected
        load using this command.

        :param impedance: the load impedance in Ohms between 50 to 1e+6 Ohm
        :param channel: the output channel int from 1 to 2
        :return: None
        """
        self.write(":OUTP%d:IMP:EXT %s;" % (channel, impedance))

    def output_impedance(self, channel=1):
        """
        Use this command to query the source impedance of the output connectors.
        Note that only two settings are available: 50 Ω or 1 kΩ. If you try
        to program any other value, it will be rounded to one of the specified
        values.

        :param channel: the output channel int from 1 to 2
        :return:
        """
        return float(self.ask(":OUTP%d:IMP?" % channel))

    def set_output_impedance(self, impedance, channel=1):
        """
        Use this command to set the source impedance of the output connectors.
        Note that only two settings are available: 50 Ω or 1 kΩ. If you try
        to program any other value,
        it will be rounded to one of the specified values.

        :param channel: the output channel int from 1 to 2
        :param impedance: the output impedance 50 Ω or 1 kΩ
        :return:
        """
        self.write(":OUTP%d:IMP %g" % (channel, impedance))

    ############################################################################
    #                      Trigger configuration                               #
    ############################################################################
    def trigger_source(self) -> TriggerSourceType:
        """
        This command queries the instrument trigger source. This source can be
        ``external``, ``manual``, ``immediate`` or ``internal``.

        Note: immediate and internal are equivalent

        :return: the trigger source
        """
        source = str(self.ask(":ARM:SOUR?")).capitalize().strip()
        trigger_source = {'external': 'EXT', 'manual': 'MAN',
                          'immediate': 'IMM', 'internal': 'INT'}

        for k, v in trigger_source:
            if source == v:
                return k

        raise ValueError("unexpected return from the tool")

    def set_trigger_source(self, source: TriggerSourceType = 'external'):
        """
        This command set the instrument trigger source. This source can be
        ``external``, ``manual``, ``immediate`` or ``internal``.

        Note: immediate and internal are equivalent

        :param source: the trigger source
        """
        trigger_source = {'external': 'EXT', 'manual': 'MAN',
                          'immediate': 'IMM', 'internal': 'INT'}

        self.write(":ARM:SOUR %s" % trigger_source[source])

    def trigger_impedance(self):
        """
        Not implemented !!! This command queries the trigger input impedance;
        it can be 50 Ohm or 1KOhm

        :return: the trigger input impedance: '50ohm', '1kohm'
        """
        raise NotImplemented('Not implemented')

    def set_trigger_impedance(
            self, impedance: Literal['50ohm', 'high'] = '50ohm') -> None:
        """
        This command sets the trigger input impedance; it can
        be 50 Ohm or high (that correspond to 10 kOhm)

        :param impedance: trigger input impedance '50ohm', 'high'
        :return: None
        """

        if impedance.lower().strip() == 'high':
            impedance = '10kohm'

        self.write("ARM:IMP %s" % impedance)

    def trigger_threshold(self) -> float:
        """
        This command queries the trigger input threshold voltage level.

        :return the threshold: from -10V to 10V
        """
        return float(self.ask("ARM:LEV?"))

    def set_trigger_threshold(self, threshold: float) -> None:
        """
        This command sets the trigger input threshold voltage level.

        :param threshold: from -10V to 10V
        """
        self.write("ARM:LEV %g" % threshold)

    def trigger_slope(self) -> str:
        """
        Not implemented ! This command queries the instrument trigger input
        slope. The slope can be rising, falling

        :return the trigger slope
        """
        raise NotImplemented('Not implemented')

    def set_trigger_slope(self, slope: Literal['rising', 'falling']) -> None:
        """
        This command sets  the instrument trigger input slope.
        The slope can be rising, falling

        :return the trigger slope
        """
        slope = "POS" if slope.lower().strip() == 'rising' else "NEG"
        self.write("ARM:SLOP %s" % slope)

    def trigger_arm(self):
        """This command do nothing, it is her for compatibility"""
        pass

    def trigger_disarm(self):
        """"This command do nothing, it is her for compatibility"""
        pass

    def trigger_mode(self):
        """
        (Not implemented) This command queries the instrument trigger mode.

        :return a key of the :code:TRIGGER_MODE dictionary 'gated', 'single', 'continuous'
        """
        raise NotImplemented('Not implemented')

    def set_trigger_mode(self, mode: Literal['gated', 'single']) -> None:
        """
         This command set the instrument trigger source.

        :param mode: 'gated' 'single'
        :return: None
        """

        mode = mode.lower().strip()
        if mode == 'gated':
            self.write("TRIG:SOUR EXT")
        elif mode == 'single':
            self.write("TRIG:SOUR IMM")
            self.write(":TRIG:COUN 1")
        elif mode == 'burst':
            raise NotImplemented('Not implemented')
        elif mode == 'continuous':
            raise NotImplemented('Not implemented')

        raise NotImplemented('Not implemented')
        # self.write("TRIG:MODE %s" % mode)

    def trigger(self):
        self.write("*TRG")
        time.sleep(0.001)

    ############################################################################
    #                            Pulse configuration                           #
    ############################################################################
    def set_pulse_edge_auto(self, auto: bool = True, channel: int = 1) -> None:
        """
        Use this command to set the automatic coupling of the pulse
        trailing-edge transition-time to the leading-edge transition-time.

        :param auto: True of auto mode on, false for auto mode off
        :param channel: the output channel int from 1 to 2
        """

        self.write(':PULS:TRAN%d:TRA:AUTO %s' % (channel, self._is_off_str(auto)))

    def pulse_edge_auto(self, channel: int = 1) -> str:
        """
        Use this command to query the automatic coupling of the pulse
        trailing-edge transition-time to the leading-edge transition-time.

        :param channel: the output channel int from 1 to 2
        """

        return self.write(':PULS:TRAN%d:TRA:AUTO?' % channel)

    def set_pulse_edge(self, leading: float = 2E-9, trailing: float = 2E-9, channel: int = 1) -> None:
        """
        Sets the pulse edge time on the leading and trailing, edges of a pulse.
        Set in second between 8.4E-9 and 1E-6

        if trailing and leading is not equal, this function deactivates
        the pulse_edge_auto

        :param leading: leading edge in s between 2.00E-9 to 200E-3
        :param trailing: trailing edge in s between 2.00E-9 to 200E-3
        :param channel: the output channel int from 1 to 2
        """

        if leading != trailing:
            self.set_pulse_edge_auto(False, channel=channel)

        self.write(':PULS:TRAN%d:TRA %gS' % (channel, trailing))
        self.write(':PULS:TRAN%d:LEAD %gS' % (channel, leading))

    def pulse_edge(self, channel: int = 1) -> Tuple[float, float]:
        """
        Query the pulse edge time on the leading and trailing, edges of a pulse.
        Set in second between 8.4E-9 and 1E-6

        :param channel: the output channel int from 1 to 2
        :return: a tuple (leading, trailing)
        """

        trailing = float(self.ask(':PULS:TRAN%d:TRA?' % channel))
        leading = float(self.ask(':PULS:TRAN%d:LEAD?' % channel))

        return leading, trailing

    # noinspection PyUnusedLocal
    def set_delay(self, delay, pulse_nb: int = 1, channel: int = 1) -> None:
        """
        his command sets the pulse delay for the specified
        pulse relative to the selected output channel.

        :param delay: the pulse delay in seconds
        :param pulse_nb: not used, for compatibility
        :param channel: the output channel int from 1 to 4
        """

        self.write("PULS:DEL%d %gS" % (channel, delay))

    # noinspection PyUnusedLocal
    def delay(self, pulse_nb: int = 1, channel: int = 1) -> float:
        """
        his command  queries the pulse delay for the specified
        pulse relative to the selected output channel.

        :param pulse_nb: not used, for compatibility
        :param channel: the output channel int from 1 to 4
        :return: the pulse delay in seconds
        """
        return float(self.ask("PULS:DEL%d?" % channel))

    # noinspection PyUnusedLocal

    def pulse_width(self, pulse_nb=1, channel=1):
        """
        This command queries the pulse width for the specified pulse relative
        to the selected output channel.

        Pulse Width = Period × Duty Cycle / 100.
        The pulse width must be less than the period.
        Pulse Width ≤ Pulse Period

        :param channel: the output channel int from 1 to 2
        :param pulse_nb: unused (kept for compatibility)
        :return: the pulse width
        """
        return self.ask(":PULS:WIDT%d?" % channel)

    # noinspection PyUnusedLocal
    def set_pulse_width(self, pulse_width, channel=1, pulse_nb=1, unit='s'):
        """
        This command sets the pulse width for the specified pulse relative
        to the selected output channel.

        Pulse Width = Period × Duty Cycle / 100.
        The pulse width must be less than the period.
        Pulse Width ≤ Pulse Period

        :param pulse_width: the pulse with in ``UNIT``
        :param channel: the output channel int from 1 to 2
        :param pulse_nb: unused (kept for compatibility)
        :param unit: the unit of time. has to be a key of ``UNIT`` : 's', 'ms', 'us', 'ns'
        :return: None
        """
        self.write(":PULS:WIDT%d %g%s" % (channel, pulse_width, self.UNIT[unit]))

    def polarity(self, channel=1):
        """
        This command query the output polarity

        :param channel: the output channel int from 1 to 2
        :return: the polarity, as a key of `POLARITIES` dictionary ('positive', 'negative')
        """
        if (self.ask(":OUTP%d:POL?" % channel)).strip() == "NORM":
            return 'positive'
        else:
            return 'negative'

    def set_polarity(self, pol='positive', channel=1):
        """
        This command set the output polarity

        :param pol: the polarity, as a key of `POLARITIES` dictionary ('positive' 'negative')
        :param channel: the output channel int from 1 to 2
        :return: None
        """
        self.write(":OUTP%d:POL %s;" % (channel, self.POLARITIES[pol]))

    def amplitude(self, channel=1):
        """
        This command queries the output amplitude for the specified
        output channel.

        :param channel: the output channel int from 1 to 2
        :return: the amplitude in V
        """
        self.write(":HOLD:VOLT")
        return float(self.ask("VOLT%d?" % channel))

    def set_amplitude(self, amplitude, channel=1):
        """
        This command sets the output amplitude for the specified output channel.

        :param amplitude: the amplitude in V
        :param channel: the output channel int from 1 to 2
        """
        self.write("SOUR:VOLT%d:LEV:AMPL %g;" % (channel, amplitude))

    def offset(self, channel=1):
        """
        This query the offset voltage of the output signal.

        :param channel: the output channel int from 1 to 2
        :return: the offset in V
        """
        return float(self.ask(":VOLT%d:OFFS?" % channel))

    def set_offset(self, offset, channel=1):
        """
        This set the offset voltage of the output signal.

        :param offset: the offset in V
        :param channel: the output channel int from 1 to 2
        :return:
        """
        self.write(":VOLT%d:OFFS %gV;" % (channel, offset))

    def low_amplitude(self, channel=1):
        """
        This command queries the low level of the output amplitude
        for the specified channel

        :param channel: the output channel int from 1 to 2
        :return: The amplitude in V
        """
        return float(self.ask(":VOLT%d:LOW?" % channel))

    def set_low_amplitude(self, amplitude, channel=1):
        """
        This command sets the low level of the output amplitude
        for the specified channel

        :param amplitude: the amplitude in V
        :param channel: the output channel int from 1 to 2
        :return: None
        """
        self.write(":VOLT%d:LEV:LOW %.2f;" % (channel, amplitude))

    def high_amplitude(self, channel=1):
        """
        This command queries the high level of the output amplitude
        for the specified channel

        :param channel: the output channel int from 1 to 2
        :return: The amplitude in V
        """
        return float(self.ask(":VOLT%d:HIGH?" % channel))

    def set_high_amplitude(self, ampl, channel=1):
        """
        This command sets the high level of the output amplitude
        for the specified channel

        :param ampl: the amplitude in V
        :param channel: the output channel int from 1 to 2
        :return: None
        """
        self.write(":VOLT%d:LEV:HIGH %.2f;" % (channel, ampl))

    def pulse_mode(self, channel=1):
        """
        This command queries the pulse mode for the selected output channel.

        :param channel: the output channel int from 1 to 2
        :return: a key of :code:PULSE_MODE (ie. ('double', 'single'))
        """
        if int(self.ask(":PULS:DOUB%d?" % channel)) == 1:
            return 'double'
        else:
            return 'single'

    def set_pulse_mode(self, mode='single ', channel=1):
        """
        This command sets the pulse mode for the selected output channel.

        :param mode: a :code:PULSE_MODE key
        :param channel: the output channel int from 1 to 2
        """
        self.write(":PULS:DOUB%d %s" % (channel, self.PULSE_MODE[mode]))

    def config_single_pulse_by_amp(self, amplitude: float, width: float,
                                   offset: float = 0, channel: int = 1):

        if amplitude >= 0:
            if self.polarity(channel=channel) == 'negative':
                # if not the right one, set the amplitude to somthing small
                self.write(":SOUR:VOLT%d:LEV:HIGH %f;LOW %f;" % (channel, 0.1, 0))
                # change the polarity
                self.set_polarity('positive', channel)

            # set the wanted amplitude
            self.write(":SOUR:VOLT%d:LEV:HIGH %f;LOW %f;" % (channel, amplitude, offset))

        else:
            if self.polarity(channel=channel) == 'positive':

                # if not the right one, set the amplitude to somthing small
                self.write(":SOUR:VOLT%d:LEV:HIGH %f;LOW %f;" % (channel, 0.0, -0.1))

                # change the polarity
                self.set_polarity('negative', channel)
            # set the wanted amplitude
            self.write(":SOUR:VOLT%d:LEV:HIGH %f;LOW %f;" % (channel, offset, amplitude))

        self.set_pulse_width(width, channel)

    ############################################################################
    #                                    System                                #
    ############################################################################

    def error(self):
        """
        Returns a tuple of an error code and message from a single error.
        """
        err = self.values(":system:error?")
        if len(err) < 2:
            err = self.read()  # Try reading again
        code = err[0]
        message = err[1].replace('"', '')
        return code, message

    def check_errors(self):
        """
        Logs any system errors reported by the instrument.
        """
        code, message = self.error
        while code != 0:
            t = time.time()
            log.info("Agilent 81110 reported error: %d, %s", code, message)
            code, message = self.error
            if (time.time() - t) > 10:
                log.warning("Timed out for AT PG-1074 error retrieval.")

    def reset(self):
        """ Resets the instrument and clears the tool.  """
        self.write("*RST;")
        self.write("*CLS;")
        self.write(":STAT:PRES;")

    def shutdown(self):
        """ Ensures that the current or voltage is turned to zero
        and disables the output. """
        for i in (1, 2):
            self.set_output(False, i)

        time.sleep(0.01)  # a bit of time before one can close the Visa session

        self.isShutdown = True
        log.info("Shutting down %s.", self.name)
