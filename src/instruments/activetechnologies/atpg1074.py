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
import time
from typing import Literal, Final

import pyvisa

from .. import Instrument
from ...adapters import VISAAdapter

# Setup logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

MILLI = 10 ** -3
MICRO = 10 ** -6
NANO = 10 ** -9

__all__ = ['ATPG1074', 'timeout_connect_workaround',
           "TimeUnitType", "PulseModeType", "TriggerSourceType"]

TimeUnitType: Final = Literal['s', 'ms', 'us', 'ns']
PulseModeType: Final = Literal['externalwidth', 'quadruple', 'triple', 'double', 'single']
TriggerSourceType: Final = Literal['timer', 'external', 'manual']


def timeout_connect_workaround(address: str, wait_time=1, attempt=10):
    """
    try ``attempt`` time to connect to the ATPG1074 and waite wait_time in
    between. This function is a workaround to avoid the timeout problem with
    this tool

    :param address: The Visa address for the tool
    :param wait_time: the time between two attempts (in s)
    :param attempt: the number of attempt before raising an error (VisaIOError)

    :raise VisaIOError: when the number of attempt ir reached without success
    """
    for a in range(attempt):
        try:
            time.sleep(wait_time)
            pg_adapter = VISAAdapter(address)
            return pg_adapter
        except pyvisa.errors.VisaIOError as e:
            time.sleep(1)
            if a == attempt - 1:
                raise e


class ATPG1074(Instrument):
    """ Represents the Active technology pulse generator PG1074 and provides a
    high-level interface for interacting with the instrument.
    """

    POLARITIES = {'positive': 'OFF', 'negative': 'ON'}

    PULSE_MODE = {'externalwidth': 'EXTERNALWIDTH', 'quadruple': 'QUADRUPLE',
                  'triple': 'TRIPLE', 'double': 'DOUBLE', 'single': 'SINGLE'}

    TRIGGER_MODE = {'gated': 'GATED', 'single': 'SINGLE',
                    'burst': 'BURST', 'continuous': 'CONTINUOUS'}

    TRIGGER_SOURCE = {'timer': 'TIM', 'external': 'EXT', 'manual': 'MAN'}

    CHANNEL_NUMBER: Final[int] = 4
    """ The number of channels available """

    MINIMUM_AMPLITUDE: Final[float] = 10 * MILLI
    """ The minimum pulse amplitude (in voltage) the PG can send """

    MINIMUM_PULSEWIDTH: Final[float] = 0.7 * NANO
    """ The minimum pulse width (in second) the PG can send """

    def __init__(self, adapter, **kwargs):
        super(ATPG1074, self).__init__(
            adapter, "AT PG 1074", **kwargs
        )

    @staticmethod
    def _is_off_str(str_or_bool):
        if str(str_or_bool).strip().capitalize() == 'OFF' \
                or (type(str_or_bool) is bool and str_or_bool is False) \
                or (type(str_or_bool) is int and str_or_bool == 0):
            return 'OFF'
        else:
            return 'ON'

    ############################################################################
    #                    output configuration                                  #
    ############################################################################

    def set_output(self, on_off: bool = False, channel: int = 1) -> None:
        """
        This command enables or disables a channel of the pulse generator.

        :param on_off: boolean True : enable, False : disables
        :param channel: the output channel int from 1 to 4
        :return: None
        """
        self.write("OUTP%d:STAT %s" % (channel, self._is_off_str(on_off)))

    def enable(self, channel=1) -> None:
        """"
        This command enables a channel of the pulse generator output.

        :param channel: the output channel int from 1 to 4
        :return: None
        """
        self.write("OUTP%d:STAT ON" % channel)

    def disables(self, channel: int = 1) -> None:
        """"
        This command disables a channel of the pulse generator output.

        :param channel: the output channel int from 1 to 4
        :return: None
        """
        self.write("OUTP%d:STAT OFF" % channel)

    def output(self, channel: int = 1) -> int:
        """
        returns the output state of the  channel :code:channel

        :param channel:the output channel int from 1 to 4
        :return: boolean True: enable, False: disables
        """
        return int(self.ask("OUTP%d:STAT?" % channel)) > 0

    def load_compensation(self, channel: int = 1) -> int:
        """
        This command query the automatic calculation of the load impedance for
        the selected output channel.

        If the load compensation is set to ON, the value set through the command
        SOUR1:LOAD:IMP will be ignored.

        IMPORTANT NOTE: you can send this command only when the instrument
        is in stopped state.

        :param channel: the output channel int from 1 to 4
        :return: return False if the automatic load compensation is OFF, True otherwise
        """
        return int(self.ask("SOUR%d:LOAD:COMP?" % channel)) > 0

    def set_load_compensation(self, on_off: bool = False, channel: int = 1) -> None:
        """
        This command set the automatic calculation of the load impedance for the
        selected output channel.

        If the load compensation is set to ON, the value set through the command
        SOUR1:LOAD:IMP will be ignored.

        IMPORTANT NOTE: you can send this command only when the instrument is in
        stopped state.

        :param on_off: boolean True : ON, False: OFF
        :param channel: the output channel int from 1 to 4
        :return: None
        """
        self.write("SOUR%d:LOAD:COMP %s" % (channel, self._is_off_str(on_off)))

    def load_impedance(self, channel: int = 1) -> int:
        """
        This command queries the load impedance value for the selected output channel

        :param channel: the output channel int from 1 to 4
        :return: the load impedance in Ohms
        """
        return float(self.ask("SOUR%d:LOAD:IMP?" % channel)) > 0

    def set_load_impedance(self, impedance: float = 50, channel: int = 1) -> None:
        """
        This command sets the load impedance value for the selected output channel

        :param impedance: the load impedance in Ohms between 50 to 1E+08 Ohm
        :param channel: the output channel int from 1 to 4
        :return: None
        """
        self.write("SOUR%d:LOAD:IMP %g" % (channel, impedance))

    ############################################################################
    #                          pulse configuration                             #
    ############################################################################
    def polarity(self, channel: int = 1):
        """
        This command query the output polarity

        :param channel: the output channel int from 1 to 4
        :return: the polarity: 'positive' or 'negative'
        """
        if int(self.ask("SOUR%d:INV?" % channel)) == 0:
            return 'positive'
        else:
            return 'negative'

    def set_polarity(self,
                     polarity: Literal['positive', 'negative'] = 'positive',
                     channel: int = 1) -> None:
        """
        This command set the output polarity

        :param polarity: the polarity: 'positive' or 'negative'
        :param channel: the output channel int from 1 to 4
        """
        self.write("SOUR%d:INV %s" % (channel, self.POLARITIES[polarity]))

    def amplitude(self, channel: int = 1) -> float:
        """
        This command queries the output amplitude for the specified output channel.
        :param channel: the output channel int from 1 to 4
        :return: the amplitude in V
        """
        return float(self.ask("SOUR%d:VOLT:AMPL?" % channel))

    def set_amplitude(self, amplitude, channel: int = 1) -> None:
        """
        This command sets the output amplitude for the specified output channel.
        :param amplitude: the amplitude in V
        :param channel: the output channel int from 1 to 4
        :return: None
        """
        self.write("SOUR%d:VOLT:AMPL %g" % (channel, amplitude))

    def offset(self, channel: int = 1) -> float:
        """
        This command queries the offset voltage for the specified
        output channel.

        :param channel: the output channel int from 1 to 4
        :return: the offset in V
        """
        return float(self.ask("SOUR%d:VOLT:LEV:IMM:OFFS?" % channel))

    def set_offset(self, offset, channel: int = 1) -> None:
        """
        This command sets the offset voltage for the specified
        output channel.

        :param offset: the offset in V
        :param channel: the output channel int from 1 to 4
        :return: None
        """
        self.write("SOUR%d:VOLT:LEV:IMM:OFFS %g" % (channel, offset))

    def low_amplitude(self, channel: int = 1) -> float:
        """
        This command queries the low level of the output amplitude for
        the specified channel

        :param channel: the output channel int from 1 to 4
        :return: The amplitude in V
        """
        return float(self.ask("SOUR%d:VOLT:LEVel:IMM:LOW?" % channel))

    def set_low_amplitude(self, amplitude: float, channel: int = 1) -> None:
        """
        This command sets the low level of the output amplitude
        for the specified channel

        :param amplitude: the amplitude in V
        :param channel: the output channel int from 1 to 4
        :return: None
        """
        self.write("SOUR%d:VOLT:LEVel:IMM:LOW %gV" % (channel, amplitude))

    def high_amplitude(self, channel: int = 1) -> float:
        """
        This command queries the high level of the output amplitude
        for the specified channel

        :param channel: the output channel int from 1 to 4
        :return: The amplitude in V
        """
        return float(self.ask("SOUR%d:VOLT:LEVel:IMM:HIGH?" % channel))

    def set_high_amplitude(self, amplitude, channel: int = 1) -> None:
        """
        This command sets the high level of the output amplitude
        for the specified channel

        :param amplitude: the amplitude in V
        :param channel: the output channel int from 1 to 4
        """
        self.write("SOUR%d:VOLT:LEVel:IMM:HIGH %gV" % (channel, amplitude))

    def set_delay(self, delay: float, pulse_nb: int = 1, channel: int = 1) -> None:
        """
        This command sets the pulse delay for the specified
        pulse relative to the selected output channel.

        :param delay: the pulse delay in seconds
        :param pulse_nb: if set up in multipulse mode the pulse number, should be 1 otherwise
        :param channel: the output channel int from 1 to 4
        """
        self.write("SOUR%d:PULS%d:DELay %.10fs" % (channel, pulse_nb, delay))

    def delay(self, pulse_nb: int = 1, channel: int = 1) -> float:
        """
        his command  queries the pulse delay for the specified
        pulse relative to the selected output channel.

        :param pulse_nb: if set up in multipulse mode the pulse number, should be 1 otherwise
        :param channel: the output channel int from 1 to 4
        :return: the pulse delay in seconds
        """
        return float(self.ask("SOUR%d:PULS%d:DELay?" % (channel, pulse_nb)))

    def set_initial_delay(self, delay: float, channel: int = 1) -> None:
        """
        Set the output ``channel`` initial delay
        :param delay: the pulse delay in seconds
        :param channel: the output channel int from 1 to 4
        """
        self.write("SOURce%d:INITDELay %.10f" % (channel, delay))

    def initial_delay(self, channel: int = 1) -> float:
        """
        Get the output ``channel`` initial delay
        :param channel: the output channel int from 1 to 4
        """
        return float(self.ask("SOURce%d:INITDELay?" % channel))

    def pulse_width(self, pulse_nb: int = 1, channel: int = 1) -> float:
        """
        This command queries the pulse width for the specified pulse relative
        to the selected output channel.

        Pulse Width = Period × Duty Cycle / 100.
        The pulse width must be less than the period.
        Pulse Width ≤ Pulse Period

        :param channel: the output channel from 1 to 4
        :param pulse_nb: the pulse number from 1 to 4
        :return: the pulse width in seconds
        """
        return float(self.ask("SOUR%d:PULS%d:WID?" % (channel, pulse_nb)).rstrip())

    def set_pulse_width(self, w, pulse_nb: int = 1,
                        unit: TimeUnitType = 's', channel: int = 1) -> None:
        """
        This command sets the pulse width for the specified pulse relative
        to the selected output channel.

        Pulse Width = Period × Duty Cycle / 100.
        The pulse width must be less than the period.
        Pulse Width ≤ Pulse Period

        :param w: the pulse width in :code:UNIT
        :param channel: the output channel int from 1 to 4
        :param pulse_nb: the pulse number int from 1 to 4
        :param unit: the unit of time. has to be 's', 'ms', 'us', 'ns'
        :return: None
        """
        self.write("SOUR%d:PULS%d:WID %g %s" % (channel, pulse_nb, w, unit))

    def pulse_mode(self, channel: int = 1):
        """
        This command queries the pulse mode for the selected output channel.

        It sets how many pulses will be available for the selected output;
        If EXTernalWIDth is selected it means that the Trigger In signal is
        directly routed to the selected output.

        :param channel: the output channel int from 1 to 4
        :return: the pulse mode : 'externalwidth', 'quadruple', 'triple', 'double' or 'single'
        """
        return str(self.ask("OUTP%d:PULS:MODE?" % channel)).capitalize().rstrip()

    def set_pulse_mode(self, mode: PulseModeType = 'single', channel: int = 1) -> None:
        """
        This command sets the pulse mode for the selected output channel.

        It sets how many pulses will be available for the selected output;
        If 'external width' is selected it means that the Trigger In signal
        is directly routed to the selected output.

        :param channel: the output channel int from 1 to 4
        :param mode: an available mode : 'external width', 'quadruple', 'triple', 'double', 'single'
        :return: none

        """
        self.write("OUTP%d:PULS:MODE %s" % (channel, self.PULSE_MODE[mode]))

    def config_single_pulse_by_amp(self, amplitude: float, width: float,
                                   offset: float = 0, channel: int = 1) -> None:
        """
        configure the pulse generator to send a pulse with the characteristics
        given in parameters. The pulse will be between ``offset`` and
        ``amplitude``. The function will configure the right polarity

        The pulse generator must be already configure in single mode and with
        the wanted delay and impedance.

        :param amplitude: the pulse amplitude in V
        :param width: the pulse width in s
        :param offset: the amplitude offset in V
        :param channel: the output channel int from 1 to 4
        """
        if amplitude >= 0:
            if self.polarity(channel=channel) == 'negative':
                self.write(":SOUR%d:VOLT:LEV:IMM:LOW %fV;HIGH %fV;" % (channel, -0.01, 0.00))
                self.set_polarity('positive', channel)
                self.write(":SOUR%d:VOLT:LEV:IMM:HIGH %fV;LOW %fV;" % (channel, 0.01, 0.0))

            self.write(":SOUR%d:VOLT:LEV:IMM:HIGH %fV;LOW %fV;" % (channel, amplitude, offset))

        else:
            if self.polarity(channel=channel) == 'positive':
                self.write(":SOUR%d:VOLT:LEV:IMM:HIGH %fV;LOW %fV;" % (channel, 0.01, 0.00))
                self.set_polarity('negative', channel)
                self.write(":SOUR%d:VOLT:LEV:IMM:LOW %fV;HIGH %fV;" % (channel, -0.01, 0.0))

            self.write(":SOUR%d:VOLT:LEV:IMM:HIGH %fV;LOW %fV;" % (channel, offset, amplitude))

        self.set_pulse_width(width, channel=channel)

    def set_number_cycles(self, ncycles: int, channel: int) -> None:
        """This command sets the number of cycles (burst count) to
            be output in burst mode for the specified output channel.

        :param ncycles: the number of repetition per burst
        :param channel: the output channel int from 1 to 4
        """
        self.write("SOURce%d:BURSt:NCYCles %d" % (channel, ncycles))

    def set_period(self, period: float, channel: int) -> None:
        """This command sets the period for the output channel

        :param period: the period in seconds
        :param channel: the output channel int from 1 to 4
        """
        self.write("SOURce%d:PERiod %g" % (channel, period))

    ############################################################################
    #                          Marker configuration                            #
    ############################################################################
    # noinspection PyUnusedLocal
    def marker_polarity(self, channel: int = 1, marker_channel: int = 1):

        """
        This command queries the trigger output polarity; the polarity
        can be positive or negative.

        :param marker_channel: not used, for compatibility
        :param channel: not used, for compatibility
        :return: the polarity: 'positive' or 'negative'
        """

        return str(self.ask("TRIG:OUTP:POL?")).strip().lower()

    # noinspection PyUnusedLocal
    def set_marker_polarity(
            self,
            polarity: Literal['positive', 'negative'] = 'positive',
            channel: int = 1, marker_channel: int = 1) -> None:
        """
        This command sets the trigger output polarity; the polarity
        can be positive or negative.

        :param marker_channel: not used, for compatibility with other PG tools
        :param channel: not used, for compatibility  with other PG tools
        :param polarity: the polarity: 'positive' or 'negative'
        :return: None
        """
        self.write("TRIG:OUTP:POL %s" % polarity)

    # noinspection PyUnusedLocal
    def marker_amplitude(self, channel: int = 1, marker_channel: int = 1) -> float:
        """
        This command queries the trigger output voltage level

        :param marker_channel: not used, for compatibility with other PG tools
        :param channel: not used, for compatibility with other PG tools
        :return: the amplitude in V
        """
        return float(self.ask("TRIG:OUTP:AMPL?"))

    # noinspection PyUnusedLocal
    def set_marker_amplitude(self, amplitude: float,
                             channel: int = 1, marker_channel: int = 1) -> None:
        """
        This command sets the trigger output voltage level

        :param marker_channel: not used, for compatibility with other PG tools
        :param channel: not used, for compatibility with other PG tools
        :param amplitude: the amplitude in V, between 0.9 and 1.65
        :return: None
        """
        self.write("TRIG:OUTP:AMPL %g" % amplitude)

    # noinspection PyUnusedLocal
    def marker_delay(self, channel: int = 1, marker_channel: int = 1) -> float:
        """
        This command queries the trigger output delay in s
        :param marker_channel: not used, for compatibility with other PG tools
        :param channel: not used, for compatibility with other PG tools
        """
        return float(self.ask("TRIGger:OUTPut:DELay?"))

    # noinspection PyUnusedLocal
    def set_marker_delay(self, delay: float,
                         channel: int = 1, marker_channel: int = 1) -> None:
        """
        This command set the trigger output delay in s

        :param delay:  the delay in seconds
        :param marker_channel: not used, for compatibility with other PG tools
        :param channel: not used, for compatibility with other PG tools
        """
        self.write("TRIGger:OUTPut:DELay %g" % delay)

    ############################################################################
    #                          Trigger configuration                           #
    ############################################################################
    def trigger_mode(self):
        """
        This command queries the instrument trigger mode.
        The trigger mode can be : gated, single, burst, continuous

        :return a trigger mode: 'gated', 'single', 'burst', 'continuous'
        """
        return str(self.ask("TRIG:MODE?")).capitalize().rstrip()

    def set_trigger_mode(
            self,
            mode: Literal['gated', 'single', 'burst', 'continuous'] = 'single') -> None:
        """
        This command set the instrument trigger source.
        The trigger mode can be : gated, single, burst, continuous

         :param mode: the wanted mode
        """
        self.write("TRIG:MODE %s" % self.TRIGGER_MODE[mode])

    def trigger_slope(self) -> Literal['rising', 'falling']:
        """
        This command queries the instrument trigger input slope.
        The slope can be rising, falling

        :return the trigger slope
        """
        # noinspection PyTypeChecker
        return self.ask("TRIG:SLOPe?").lower().strip(" \n\"")

    def set_trigger_slope(self, slope: Literal['rising', 'falling']) -> None:
        """
        This command sets  the instrument trigger input slope.
        The slope can be rising, falling

        :param slope: the trigger slope 'rising' or 'falling'
        """
        self.write("TRIG:SLOPe %s" % slope)

    def trigger_threshold(self) -> float:
        """
        This command queries the trigger input threshold voltage level.

        :return the threshold: from 0.9V to 1.650V
        """
        return float(self.ask("TRIG:THRE?"))

    def set_trigger_threshold(self, threshold: float) -> None:
        """
        This command sets the trigger input threshold voltage level.

        :param threshold: from 0.9V to 1.65V
        """
        self.write("TRIG:THRE %gV" % threshold)

    def trigger_source(self) -> TriggerSourceType:
        """
        This command queries the instrument trigger source.

        The trigger source can be :

           =========== ============================================
           source      Description
           =========== ============================================
           timer       internal timer
           external    lock on trigger in SMA input
           manual      lock on trigger key or trigger() command
           =========== ============================================

        :return a source from the table
        """
        # noinspection PyTypeChecker
        return str(self.ask("TRIG:SOUR?")).capitalize().strip(" \n\"")

    def set_trigger_source(self, source: TriggerSourceType = 'manual') -> None:
        """
        This command set the instrument trigger source.

        The trigger source can be :

           =========== ============================================
           source      Description
           =========== ============================================
           timer       internal timer
           external    lock on trigger in SMA input
           manual      lock on trigger key or trigger() command
           =========== ============================================

        :param source: a trigger sour from the table
        """
        self.write("TRIG:SOUR %s" % self.TRIGGER_SOURCE[source])

    def trigger_impedance(self):
        """
        Not implemented !! This command queries the trigger input impedance;
        it can be 50 Ohm or 1KOhm

        :return: the trigger input impedance: '50ohm', '1kohm'
        """
        raise NotImplemented('Not implemented')
        # return str(self.ask("TRIG:IMP?")).strip().lower()

    def set_trigger_impedance(
            self,
            impedance: Literal['50ohm', 'high'] = '50ohm') -> None:
        """
        This command sets the trigger input impedance; it can
        be 50 Ohm or high (that correspond to 1 kOhm)

        :param impedance: trigger input impedance '50ohm', 'high'
        :return: None
        """

        if impedance.lower().strip() == 'high':
            impedance = '1kohm'

        self.write("TRIG:IMP %s" % impedance)

    def set_trigger_delay(self, delay: float) -> None:
        """ Set the delay of the trigger output signal

        :param delay: the delay in seconds
        """
        self.write("TRIG:OUTPut:DELay %.10f" % delay)

    def trigger_arm(self) -> None:
        """This command will arm the instrument (running state) and after that
            it will be ready to receive the trigger signal"""
        self.write("PULSEGENControl:START")

    def trigger_disarm(self) -> None:
        """This command stops the instrument."""
        self.write("PULSEGENControl:STOP")

    def trigger(self) -> None:
        """
        activate the trigger if it is set to manual
        """
        self.write("*TRG")

    ############################################################################
    #                          System                                          #
    ############################################################################
    def error(self):
        """
        Returns a tuple of an error code and message from the
        fist error in the stack
        """
        err = self.values(":system:error?")
        if len(err) < 2:
            err = self.read()  # Try reading again
        code = err[0]
        message = err[1].replace('"', '')
        return code, message

    def check_errors(self) -> None:
        """ Logs any system errors reported by the instrument.
        """
        code, message = self.error()
        while code != 0:
            t = time.time()
            log.info("AT PG-1074 reported error: %d, %s", code, message)
            code, message = self.error()
            if (time.time() - t) > 10:
                log.warning("Timed out for AT PG-1074 error retrieval.")

    def reset(self) -> None:
        """ Resets the instrument and clears the tool.  """
        self.write("*RST;:stat:pres;:*CLS;")

    def shutdown(self) -> None:
        """ Ensures that the current or voltage is turned to zero
        and disables the output. """
        # self.trigger_disarm()
        for i in range(1, 5):
            self.set_output(False, i)

        self.isShutdown = True
        log.info("Shutting down %s.", self.name)
        time.sleep(0.05)
