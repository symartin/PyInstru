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
import time
from typing import cast, Final, Literal, Union

import broadbean as bb
import numpy as np
from pyvisa import VisaIOError

from .. import Instrument

log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())
NANO = 10 ** -9

TimeUnitType: Final = Literal['s', 'ms', 'us', 'ns']
VoltageUnitType: Final = Literal['Vpp', 'Vrms', 'dBm']
ModeAmplitudeModulation: Final = Literal['AM', 'FM', 'PM', 'FSK', 'BPSK', 'SUM']
Voltage: Final = Literal['MAX', 'MIN', 'DEF']
TriggerSourceType: Final = Literal['external', 'manual', 'immediate', 'internal']
FunctionType: Final = Literal['sinusoid', 'square', 'triangle', 'ramp', 'pulse',
'prbs', 'noise', 'arb', 'dc']
ModeSync: Final = Literal['normal', 'carrier', 'marker']
PolaritySync: Final = Literal['normal', 'inverted']
SourceSync: Final = Literal['normal', 'inverted']


class Keysight33500B(Instrument):
    """
    Represents the Keysight 33500 Function/Arbitrary Waveform Generator family.
    """

    def __init__(self, adapter, **kwargs):
        super().__init__(adapter, "Keysight 33500B AWG", **kwargs)

    def wait_for_operation_to_complete(self) -> None:
        """ Waits for the latest issued overlapping command to finish """
        while True:
            try:
                if int(self.ask('*OPC?')) == 1:
                    break
            except:
                pass

    ############################################################################
    #                              data waveform                               #
    ############################################################################
    def arbitrary_upload(self, name, data_points,
                         data_format: Literal['dac', 'float'] = 'float',
                         mode: Literal['ascii', 'binary'] = ascii,
                         channel=1) -> None:
        """
        Uploads an arbitrary trace into the volatile memory of the device.
        The data_points can be given as a list of integer ``dac`` values
        (ranging from -32767 to +32767) or as a list of floating point
        values (ranging from -1.0 to +1.0).

        ==================  ==================================================
        format              Description
        ==================  ==================================================
        ``dac``             Accepts list of integer values ranging from
                            -32767 to +32767. Minimum of 8 a maximum
                            of 65536 points.

        ``float``           Accepts list of floating point values ranging
                            from -1.0 to +1.0. Minimum of 8 a maximum
                            of 65536 points.
        ==================  ==================================================

        **Note:**
        the name cannot exceed 12 characters.

        :param name: The name of the trace in the volatile memory.
        :param data_points: Individual points of the trace.
        :param data_format: Defines the format of data_points.
        :param mode: mode used to transfer the waveform
        :param channel: the output chanel 1 or 2
        """
        data_format = ':DAC' if data_format == 'dac' else ''

        if mode == 'ascii':
            data_points_str = map(str, data_points)  # Turn list entries into strings
            data_string = ', '.join(data_points_str)  # Join strings with separator
            self.write("SOUR%d:DATA%s %s, %s" % (channel, data_format, name, data_string))
        else:
            element_type = 'i' if data_format == 'dac' else 'f'
            element_length = 2 if data_format == 'dac' else 4
            binary_block = self._build_binary_block_from_np(
                data_points, element_type, element_length)

            message = "SOUR%d:DATA:ARB%s %s, " % (channel, data_format, name)
            message = message.encode('ascii') + binary_block + '\n'.encode('ascii')

            self.write_raw(message)

    @staticmethod
    def _build_binary_block_from_np(
            array: np.ndarray,
            element_type: Literal['?', 'b', 'B', 'i', 'u', 'f'],
            element_length: int) -> bytes:
        """
        build a binary block from a numpy array following
        the 'ieee' specification:

        =========   =======================
        data_type   description
        =========   =======================
        '?'         boolean
        'b'         (signed) byte
        'B'         unsigned byte
        'i'         (signed) integer
        'u'         unsigned integer
        'f'         floating-point
        =========   =======================

        :param array: numpy array holding the data
        :param element_type: the machine data type (see table)
        :param element_length: nb of (8-bit) bytes encoding the data type
        :return:
        """

        array_length = len(array)
        data_length = array_length * element_length

        header = "%d" % data_length
        header = "#%d%s" % (len(header), header)
        header = bytes(header, "ascii")

        dtype = ">%s%d" % (element_type, element_length)
        binary_data = array.astype(dtype=dtype).tobytes()

        return header + binary_data

    def arbitrary_upload_from_broadbean(
            self, name: str,
            sequence: bb.Sequence) -> tuple[list[str], list[str]]:
        """
        This function allows you to convert a pulse to a series of points,
        and then send it to output channel 1 and 2"""

        f = sequence.forge()
        name_ch1 = []
        name_ch2 = []
        for element in f.keys():
            for i, subElement in enumerate(f[element]['content'].keys()):
                channel_list = list(f[element]['content'][subElement]['data'].keys())

                if 1 in channel_list:
                    wfm_ch1 = f[element]['content'][subElement]['data'][1]['wfm']

                    name_ch1.append(name + "_1_%d" % element)
                    self.arbitrary_upload(
                        name + "_1_%d" % element, wfm_ch1, mode="binary", channel=1)

                if 2 in channel_list:
                    wfm_ch2 = f[element]['content'][subElement]['data'][2]['wfm']
                    name_ch2.append(name + "_2_%d" % element)
                    self.arbitrary_upload(
                        name + "_2_%d" % element, wfm_ch2, mode="binary", channel=2)

        return name_ch1, name_ch2

    def volatile_clear(self, channel=1) -> None:
        """
        Clear all arbitrary signals from the volatile memory.

        This should be done if the same name is used continuously to load
        different arbitrary signals into the memory, since an error will occur
        if a trace is loaded which already exists in the memory.
        """
        self.write("SOUR%d:DATA:VOL:CLE" % channel)

    ############################################################################
    #                           output source function                         #
    ############################################################################

    # -------------- arbitrary --------------
    def set_fct_arbitrary_rate(self, rate: float, channel: int = 1) -> None:
        """
        sets the sample rate of the currently selected arbitrary signal.
        Valid values are 1 µSa/s to 250 MSa/s

        **Note:**
            - The sample rate and frequency parameter are not coupled when
            playing an arbitrary waveform segment. The concept of frequency
            does not apply for arbitrary waveform sequences.

            - Setting a sample rate when not in the ARB mode will not change the
             frequency. For example, if the current function is sine, setting
             sample rate has no effect until the function changes to ARB.

        :param channel: the output chanel 1 or 2
        :param rate: the rate between 1e-6 and 160e6
        """
        self.write("SOUR%d:FUNC:ARB:SRAT %g" % (channel, rate))

    def get_fct_arbitrary_rate(self, channel: int = 1) -> float:
        """
        gets the sample rate of the currently selected arbitrary signal.

        Valid values are 1 µSa/s to 250 MSa/s

        :param channel: the output chanel 1 or 2
        :return the rate between 1e-6 and 250e6
        """
        return float(self.ask("SOUR%d:FUNC:ARB:SRAT?" % channel))

    def set_fct_arbitrary_amplitude(self, amplitude: float, channel: int = 1) -> None:
        """
        sets the peak-to-peak voltage for the currently selected arbitrary signal.
        Valid values are 1 mV to 10 V.

        **Note:**

        - Limits Due to Amplitude: You can set the voltage levels to a positive
        or negative value with the restrictions shown below. Vpp is the maximum
        peak-to-peak amplitude for the selected output termination (10 Vpp into
        50 Ω or 20 Vpp into an open circuit).

        - Setting the high or low level from the remote interface can change the
         high level or low level to achieve the desired setting. In this case
         either a "Data out of range" or "Settings conflict" error will occur.
         If the high level is set below the low level, the instrument will set
         the low level 1 mV less than the high level. If the high level is set
         below the LOW limit or the instrument output specifications, the low
         level will be set to the LOW limit or instrument output specification
         and the high level will be set 1 mV above the low level. A similar set
         of rules applies if the low level is set incorrectly.

        Similarly, the low level can be set above the high level from the remote
        interface. In this case the instrument will set the high level 1 mV
        larger than the low level. If the low level is set higher than the HIGH
        limit or the instrument output specifications, the high level will be
        set to the HIGH limit or instrument output specification and the low
        level will be set 1 mV below the high level.

        Setting the high and low levels also sets the waveform amplitude and
        offset. For example, if you set the high level to +2 V and the low
        level to -3 V, the resulting amplitude is 5 Vpp, with a -500 mV offset

        :param channel: the output chanel 1 or 2
        :param amplitude : the peak to peak amplitude in volt
        """
        # hack against strange rounding in the AWG
        amplitude = amplitude if amplitude <= 4.99975 else 4.99975

        self.write("SOUR%d:FUNC:ARB:PTP %g" % (channel, amplitude))

    def get_fct_arbitrary_amplitude(self, channel: int = 1) -> float:
        """
        gets the peak-to-peak voltage for the currently selected arbitrary signal.
        Valid values are 1 mV to 10 V.

        :param channel: the output chanel 1 or 2
        :return the peak to peak amplitude in volt
        """

        return float(self.write("SOUR%d:FUNC:ARB:PTP?" % channel))

    def set_fct_arbitrary(self, name: str, channel: int = 1) -> None:
        """
        Selects an arbitrary waveform that has previously been loaded into
        volatile memory for the channel specified

        :param name: the waveform name
        :param channel: the output chanel 1 or 2
        """

        self.write("SOUR%d:FUNC:ARB %s" % (channel, name))

    def set_fct_arbitrary_adv(self,adv_method: Literal['trigger', 'srate'],
                              channel: int = 1) -> None:
        """
        Specifies the method for advancing to the next arbitrary waveform data
        point for the specified channel.
        Can be set to ``trigger`` or ``srate``.

        :param adv_method: the advance method ``trigger`` or ``srate``.
        :param channel: the output chanel 1 or 2
        """
        self.write("SOUR%d:FUNC:ARB:ADV %s" % (channel, adv_method.capitalize()))

    def get_fct_arbitrary_adv(self, channel: int = 1) -> str:
        """
        Specifies the method for advancing to the next arbitrary waveform data
        point for the specified channel.  Can be set to ``trigger`` or ``srate``.

        :return the advance method ``trigger`` or ``srate``.
        :param channel: the output chanel 1 or 2
        """
        res = str(self.ask("SOUR%d:FUNC:ARB:ADV?" % channel)).lower().strip()

        if 'trig' in res:
            return 'trigger'
        else:
            return 'srate'

    # -------------- burst --------------

    def get_fct_burst_state(self, channel: int = 1) -> bool:
        """
        return if the burst mod is active on the specified channel

        :param channel: the output chanel 1 or 2
        """
        res = str(self.ask("SOUR%d:BURS:STAT?" % channel)).lower().strip()

        if '0' in res or 'off' in res:
            return False
        else:
            return True

    def set_fct_burst_state(self, state: bool, channel: int = 1) -> None:
        """
        set if burst is active on the specified channel

        :param state: boolean to activate or deactivate the burst mode
        :param channel: the output chanel 1 or 2
        """

        _state = "ON" if state else "OFF"
        self.write("SOUR%d:BURS:STAT %s" % (channel, _state))

    def set_fct_burst_mode(self, mode: Literal['triggered', 'gated'], channel: int = 1):
        """
        Select the triggered burst mode (called "N Cycle" on the front panel) or
        external gated burst mode using

        :param mode: 'triggered' or 'gated'
        :param channel: the output chanel 1 or 2
        """
        self.write("SOUR%d:BURS:MODE %s" % (channel, mode.capitalize()))

    def get_fct_burst_mode(self, channel: int = 1) -> Literal['triggered', 'gated']:
        """
        Select the triggered burst mode (called "N Cycle" on the front panel) or
        external gated burst mode using

        :param channel: the output chanel 1 or 2
        """
        res = str(self.ask("SOUR%d:BURS:MODE?" % channel))

        if "trig" in res.lower().strip():
            return cast(Literal['triggered'], 'triggered')
        else:
            return cast(Literal['gated'], 'gated')

    def set_fct_burst_period(self, period: float, channel: int = 1) -> None:
        """
        set the period of subsequent bursts. Has to follow the equation
        burst_period > (burst_ncycles / frequency) + 1 µs.

        Valid values are 1 µs to 8000 s.

        :param period: period between two burst in second
        :param channel: the output chanel 1 or 2
        """
        self.write("SOUR%d:BURS:INT:PER %g" % (channel, period))

    def get_fct_burst_period(self, channel: int = 1) -> float:
        """
        get the period of subsequent bursts. Valid values are 1 µs to 8000 s.

        :param channel: the output chanel 1 or 2
        :return period period between two burst in second
        """
        return float(self.ask("SOUR%d:BURS:INT:PER?" % channel))

    def set_fct_burst_ncycles(self, ncycles: Union[int, Literal['infinity']],
                              channel: int = 1) -> None:
        """
        sets the number of cycles to be output when a burst is triggered.

        Valid values are 1 to 100000 or ``infinity``.

        :param ncycles: number of cycles
        :param channel: the output chanel 1 or 2
        """
        self.write("SOUR%d:BURS:NCYC %s" % (channel, ncycles))

    def fct_burst_ncycles(self, channel: int = 1) -> Union[int, Literal['infinity']]:
        """
        sets the number of cycles to be output when a burst is triggered.

        Valid values are 1 to 100000 or ``infinity``.

        :param ncycles: number of cycles
        :param channel: the output chanel 1 or 2

        :return: number of cycles
        """
        res = self.ask("SOUR%d:BURS:NCYC?" % channel)

        try:
            res_int = int(res)
        except ValueError:
            if 'inf' in res.lower():
                return cast(Literal['infinity'], 'infinity')
            else:
                raise ValueError("unexpected return from the tool")

        return res_int

    def set_function(self, function_type: FunctionType, channel: int = 1) -> None:
        """

        Set the function for the selected channel.

        Can be : 'sinusoid', 'square', 'triangle', 'ramp', 'pulse', 'prbs',
        'noise', 'arb' or 'dc'

        **Note:**
        - The selected waveform (other than an arbitrary waveform) is output
        using the previously selected frequency, amplitude, and offset voltage
        settings.

        - Arbitrary waveforms are played according to the settings specified in
        the arbitrary waveform file. Brand new arbitrary waveforms inherit the
        current arbitrary waveform settings.

        - noise generates white gaussian noise with adjustable bandwidth and
        crest factor about 3.5.

        -prbs generates random noise using Linear Feedback Shift Register
        (LFSR) user selectable methods.

        """
        self.write("SOUR%d:FUNC %s" % (channel, function_type))

    def function(self, channel: int = 1) -> FunctionType:
        """
         Get the function for the selected channel. Can be : 'sinusoid',
         'square', 'triangle', 'ramp', 'pulse', 'prbs', 'noise', 'arb' or 'dc'

        :param channel: the output chanel 1 or 2
        :return:
        """
        res = str(self.ask("SOUR%d:FUNC?" % channel)).lower().strip()

        for name in ['sinusoid', 'square', 'triangle', 'ramp',
                     'pulse', 'prbs', 'noise', 'arb', 'dc']:
            if res in name:
                return name  # type: ignore

        raise ValueError("unexpected return from the tool")

    def set_function_frequency(self, frequency, channel) -> None:
        """
        Sets the output frequency in Hz. This command is paired with
        function_pulse_period whichever one is executed last overrides the other.

        :param frequency: from 1 uHz to 120 MHz
        :param channel: the output chanel 1 or 2
        """
        self.write("SOUR%d:FREQ %g" % (channel, frequency))

    # ----------------------- pulse function -----------------------------------

    # noinspection PyUnusedLocal
    def pulse_width(self, pulse_nb: int = 1, channel: int = 1) -> float:
        """
        This command queries the pulse width for the specified pulse relative
        to the selected output channel.

        Pulse Width = Period × Duty Cycle / 100.
        The pulse width must be less than the period.
        Pulse Width ≤ Pulse Period

        :param channel: the output channel int from 1 to 2
        :param pulse_nb: the pulse number, can only be 1 (for compatibility)
        :return: the pulse width in seconds
        """
        return float(self.ask("SOUR%d:FUNC:PULS:WIDT?" % channel).rstrip())

    # noinspection PyUnusedLocal
    def set_pulse_width(self, pulse_width, pulse_nb: int = 1,
                        unit: TimeUnitType = 's', channel: int = 1) -> None:
        """
        This command sets the pulse width for the specified pulse relative to
        the selected output channel.

        Pulse Width = Period × Duty Cycle / 100.
        The pulse width must be less than the period.
        Pulse Width ≤ Pulse Period
        :param pulse_width: the pulse with in :code:UNIT
        :param channel: the output channel int from 1 to 2
        :param pulse_nb: the pulse number, can only be 1 (for compatibility)
        :param unit: the unit of time. has to be 's', 'ms', 'us', 'ns'
        :return: None
        """
        self.write("SOUR%d:FUNC:PULS:WIDT %g %s" % (channel, pulse_width, unit))

    def set_pulse_edge(self, leading: float = 8.4E-9,
                       trailing: float = 8.4E-9, channel: int = 1) -> None:
        """
        Sets the pulse edge time on the leading and trailing, edges of a pulse.
        set in second between 8.4E-9 and 1E-6

        :param leading: leading edge between 8.4E-9 and 1E-6
        :param trailing: trailing edge between 8.4E-9 and 1E-6
        :param channel: the output channel int from 1 to 2
        """
        self.write('SOUR%d:FUNC:PULSE:TRAN:LEAD %g' % (channel, leading))
        self.write('SOUR%d:FUNC:PULSE:TRAN:TRA %g' % (channel, trailing))

    def set_pulse_period(self, period: float, channel: int = 1) -> None:
        """
        Sets the period for pulse waveforms. This command is paired with the
        frequency command; the one executed last overrides the other, as
        frequency and period specify the same parameter.

        the minimum is 50E-6 s and the maximum is 1E6 s, if the pulse with is
        larger than 0.66*period, it will automatically set the pulse with
        to 0.66*period

        :param period: the repetition period in second
        :param channel: the output channel int from 1 to 2
        """

        if period * 0.66 < self.pulse_width():
            self.set_pulse_width(period * 0.66, channel=channel)

        self.write('SOUR%d:FUNC:PULSE:PER %g' % (channel, period))

    def pulse_period(self, channel: int = 1) -> float:
        """
        Gets the period for pulse waveforms. This command is paired with the
        frequency command; the one executed last overrides the other, as
        frequency and period specify the same parameter.

        the minimum is 50E-6 s and the maximum is 1E6 s

        :param channel: the output channel int from 1 to 2
        :return the repetition period in second
        """
        return float(self.ask('SOUR%d:FUNC:PULSE:PER?' % channel))

    ############################################################################
    #                         voltage Subsystem control                        #
    ############################################################################

    def set_offset(self, offset: float, channel: int = 1) -> None:
        """
        Set the voltage offset of the output waveform in V, from 0 V to +/- 5 V,
        depending on the set voltage amplitude (maximum offset = (Vmax - voltage) / 2)

        :param offset: the offset in V
        :param channel: the output chanel 1 or 2
        """
        self.write("SOUR%d:VOLT:OFFS %g V" % (channel, offset))

    def offset(self, channel: int = 1) -> float:
        """
        Get the voltage offset of the output waveform in V, from 0 V to +/- 5 V,
        depending on the set voltage amplitude (maximum offset = (Vmax - voltage) / 2)

        :param channel: the output chanel 1 or 2
        :return: the offset in V
        """
        return float(self.write("SOUR%d:VOLT:OFFS?" % channel))

    def low_amplitude(self, channel: int = 1) -> float:
        """
        This command queries the low level of the output amplitude for the
        specified channel

        :param channel: the output channel int from 1 to 4
        :return: The amplitude in V
        """
        return float(self.ask("SOUR%d:VOLT:LOW?" % channel))

    def set_low_amplitude(self, amplitude: float, channel: int = 1) -> None:
        """
        This command sets the low level of the output amplitude for the
        specified channel

        :param amplitude: the amplitude in V, From -5 V to 4.990 V
        :param channel: the output channel int from 1 to 4
        :return: None
        """
        self.write("SOUR%d:VOLT:LOW %g V" % (channel, amplitude))

    def high_amplitude(self, channel: int = 1) -> float:
        """
        This command queries the high level of the output amplitude for the
        specified channel

        :param channel: the output channel int from 1 to 2
        :return: The amplitude in V
        """
        return float(self.ask("SOUR%d:VOLT:HIGH?" % channel))

    def set_high_amplitude(self, amplitude: float, channel: int = 1) -> None:
        """
        This command sets the high level of the output amplitude for the
        specified channel.

        :param amplitude: the amplitude in V. From -5 V to 4.990 V
        :param channel: the output channel int from 1 to 2
        """
        self.write("SOUR%d:VOLT:HIGH %g V" % (channel, amplitude))

    def amplitude(self, channel: int = 1) -> float:
        """
        This command queries the output amplitude for the specified
        output channel.

        :param channel: the output channel int from 1 to 2
        :return: the amplitude in V
        """
        return float(self.ask("SOUR%d:VOLT?" % channel))

    def set_amplitude(self, amplitude: float, channel: int = 1) -> None:
        """
        This command sets the output amplitude for the specified output channel.

        :param amplitude: the amplitude in V  from 10e-3 V to 10 V
        :param channel: the output channel int from 1 to 2
        """
        self.write("SOUR%d:VOLT%g" % (channel, amplitude))

    def polarity(self, channel: int = 1) -> Literal['positive', 'negative']:
        """
        This command queries the output amplitude for the specified output channel.

        :param channel: the output channel int from 1 to 2
        :return: the amplitude in V
        """

        res = str(self.ask("OUTP%d:POL?" % channel))

        if 'norm' in res.lower().strip():
            return cast(Literal['positive'], 'positive')
        else:
            return cast(Literal['negative'], 'negative')

    def set_polarity(self, polarity: Literal['positive', 'negative'],
                     channel: int = 1) -> None:
        """
        Inverts waveform relative to the offset voltage.

        ========= =============================================================
        polarity  description
        ========= =============================================================
        positive  waveform goes in one direction at the beginning of the cycle
        negative  waveform goes in other
        ========= =============================================================

        :param polarity: ``positive`` or ``negative``
        :param channel: the output channel  1 or 2
        """
        POLARITIES = {'positive': 'NORMAL', 'negative': 'INVERTED'}

        self.write("OUTP%d:POL %s" % (channel, POLARITIES[polarity.lower().strip()]))

    def set_auto_range(self, auto: bool, channel: int = 1) -> None:
        """
        Disables or enables voltage auto ranging for all functions.

        :param auto: true to enables, false to disables
        :param channel: the output channel  1 or 2
        :return:
        """
        param = 1 if auto else 0
        self.write("SOUR%d:VOLT:RANG:AUTO %d" % (channel, param))

    def perform_auto_range(self, channel: int = 1) -> None:
        """
        performs an immediate autorange and then turns autoranging OFF
        :param channel: the output channel  1 or 2
        """
        self.write("SOUR%d:VOLT:RANG:AUTO ONCE" % channel)

    ############################################################################
    #                              output control                              #
    ############################################################################

    def enable(self, channel=1) -> None:
        """"
        This command enables a channel of the pulse generator output.

        :param channel: the output channel int from 1 to 2
        :return: None
        """
        self.write("OUTP%d 1" % channel)

    def disables(self, channel: int = 1) -> None:
        """"
        This command disables a channel of the pulse generator output.

        :param channel: the output channel int from 1 to 4
        :return: None
        """
        self.write("OUTP%d 0" % channel)

    def set_output(self, on_off: bool = False, channel: int = 1) -> None:
        """
        This command enables or disables a channel of the AWG

        :param on_off: boolean True : enable, False : disables
        :param channel: the output channel int from 1 to 2
        :return: None
        """

        cmd = 1 if on_off else 0

        self.write("OUTP%d %s" % (channel, cmd))

    def output(self, channel: int = 1) -> int:
        """
        returns the output state of the  channel :code:channel

        :param channel:the output channel int from 1 to 4
        :return: boolean True: enable, False: disables
        """

        res = int(self.ask("OUTP%d?" % channel)) > 0

        return res == 1

    ############################################################################
    #                            load compensation                             #
    ############################################################################
    def load_impedance(self, channel: int = 1) -> Union[float, Literal['infinity']]:
        """
        Gets the expected load resistance. should be the load impedance connected
        to the output. The output impedance is always 50 Ohm, this setting can
        be used to correct the displayed voltage for loads unmatched to 50 Ohm.

        Valid values are between 1 and 10 kOhm or ``infinity`` for high impedance.

        :param channel: the output channel int from 1 to 2
        :return: the load resistance
        """
        res = self.ask("OUTP%d:LOAD?" % channel)

        if str(res).lower().strip() in 'infinity':
            return cast(Literal['infinity'], 'infinity')
        else:
            return float(res)

    def set_load_impedance(self,
                           impedance: Union[float, Literal['infinity']] = 50,
                           channel: int = 1) -> None:
        """
        Gets the expected load resistance. should be the load impedance connected
         to the output. The output impedance is always 50 Ohm, this setting can
         be used to correct the displayed voltage for loads unmatched to 50 Ohm.

        Valid values are between 1 and 10 kOhm or ``infinity`` for high impedance.

        :param impedance: the load resistance
        :param channel: the output channel int from 1 to 2
        """

        if isinstance(impedance, str):
            cmd = 'infinity'
        else:
            cmd = "%g" % impedance

        self.write("OUTP%d:LOAD %s" % (channel, cmd))

    ############################################################################
    #                                     trigger                              #
    ############################################################################
    def trigger_bust_mode(self, channel=1) -> Literal['triggered', 'gated']:
        """
        get the burst mode.

        ** available modes: **

        - ``triggered`` mode : the instrument outputs a waveform for a
        number of cycles (burst count) each time a trigger is received from
        the trigger source (trigger_source).

        - In ``gated`` burst mode, the output waveform is on or off, based
        on the signal at the rear-panel Ext Trig connector. Select this
        signal's polarity using BURSt:GATE:POLarity. When the gate signal is
        true, the instrument outputs a continuous waveform. When the gate
        signal goes false, the current waveform cycle is completed and the
        instrument stops and remains at the voltage level corresponding to
        the waveform's starting burst phase. For a noise waveform, the
        output stops immediately when the gate signal goes false.

        :param channel: the output channel 1 or 2
        :return: the burst mode
        """

        res = self.ask("SOUR%d:BURSt:MODE?" % channel)

        if str(res).lower().strip() in 'triggered':
            return cast(Literal['triggered'], 'triggered')
        else:
            return cast(Literal['gated'], 'gated')

    def set_trigger_bust_mode(self, mode: Literal['triggered', 'gated'], channel=1) -> None:
        """
        Set Selects the burst mode.

        ** available modes: **

        - ``triggered`` mode : the instrument outputs a waveform for a
        number of cycles (burst count) each time a trigger is received from
        the trigger source (trigger_source).

        - In ``gated`` burst mode, the output waveform is on or off, based
        on the signal at the rear-panel Ext Trig connector. Select this
        signal's polarity using BURSt:GATE:POLarity. When the gate signal is
        true, the instrument outputs a continuous waveform. When the gate
        signal goes false, the current waveform cycle is completed and the
        instrument stops and remains at the voltage level corresponding to
        the waveform's starting burst phase. For a noise waveform, the
        output stops immediately when the gate signal goes false.

        :param mode: the burst mode
        :param channel: the output channel 1 or 2
        """

        self.write("SOUR%d:BURSt:MODE %s" % (channel, mode))

    def trigger_source(self, channel: int = 1) -> TriggerSourceType:
        """
        This command queries the instrument trigger source. This source can be
        ``external``, ``manual``, ``immediate`` or ``internal``.

        Not immediate and internal are equivalent

         ================== ====================================================

         ================== ====================================================
         ``immediate``      the instrument outputs continuously when burst mode
                            is enabled. The rate at which the burst is generated
                            is determined by BURSt:INTernal:PERiod.

         ``external``       the instrument accepts a hardware trigger at the
                            rear-panel Ext Trig connector.

         ``manual``         the instrument initiates one burst each time a bus
                            trigger (*TRG) is received.

         ``internal``       trigger events are spaced by a timer, with the
                            first trigger as soon as INIT occurs
         ================== ====================================================

        :param channel: the output channel 1 or 2
        :return a key of the trigger source
        """

        TRIGGER_SOURCE = {'external': 'EXT', 'manual': 'BUS',
                          'immediate': 'IMM', 'internal': 'TIM'}

        source = str(self.ask("TRIG%d:SOUR?" % channel)).capitalize().strip()
        for k, v in TRIGGER_SOURCE:
            if source == v:
                return k

        raise ValueError("unexpected return from the tool")

    def set_trigger_source(self, source: TriggerSourceType = 'external', channel: int = 1) -> None:
        """
        This command set the instrument trigger source. This source can be
        ``external``, ``manual``, ``immediate`` or ``internal``. Not immediate
        and internal are equivalent

        :param source: an element of the :code:TRIGGER_SOURCE dictionary
        :param channel: the output channel 1 or 2
        """

        trigger_source = {'external': 'EXT', 'manual': 'BUS',
                          'immediate': 'IMM', 'internal': 'TIM'}

        self.write("TRIG%d:SOUR %s" % (channel, trigger_source[source]))

    def trigger(self) -> None:
        """ Send a trigger signal to the function generator. """
        self.write("*TRG;*WAI")

    def trigger_arm(self) -> None:
        """
        do nothing, just for compatibility
        """
        pass

    def trigger_threshold(self, channel: int = 1) -> float:
        """
        Get the output trigger level and input trigger threshold in volts.
        The trigger threshold is one-half of the trigger level.

        :param channel: tool channel (1 or 2)
         """
        return float(self.ask("TRIG%d:LEV?" % channel))

    def set_trigger_threshold(self, threshold: float, channel: int = 1) -> None:
        """
        Sets the output trigger level and input trigger threshold in volts.
        The trigger threshold is one-half of the trigger level.

        :param threshold: from 0.9 to 3.8 V
        :param channel: tool channel (1 or 2)
        """
        self.write("TRIG%d:LEV %g" % (channel, threshold))

    def trigger_slope(self, channel: int = 1) -> str:
        """
        Specifies polarity of trigger signal on rear-panel Trig-In connector
        for any externally-triggered mode.

        :return: the trigger slope
        """
        return str(self.ask("TRIG%d:SLOP?" % channel))

    def set_trigger_slope(self, slope: Literal['rising', 'falling'], channel: int = 1) -> None:
        """
        Specifies polarity of trigger signal on rear-panel Trig-In connector
        for any externally-triggered mode.

        :return: the trigger slope
        """
        slope = "POS" if slope.lower().strip() == 'rising' else "NEG"
        self.write("TRIG%d:SLOP %s" % (channel, slope))

    def set_delay(self, delay, channel=1):
        """
        Sets trigger delay, (time from assertion of trigger to occurrence of
        triggered event). This source can be ``external``, ``manual``,
        ``immediate`` or ``internal``.

        :param delay: the delay in s: from 0 to 1000 s, in resolution of 4 ns; default 0
        :param channel: the output channel 1 or 2
        """
        self.write("TRIG%d:DELay %s" % (channel, delay))

    ############################################################################
    #                            Utilities                                     #
    ############################################################################

    def wait_for_trigger(self, timeout=3600, should_stop=lambda: False) -> None:
        """
        Wait until the triggering has finished or timeout is reached.

        :param timeout: The maximum time the waiting is allowed to take. If
        timeout is exceeded, a TimeoutError is raised. If timeout is set to
        zero, no timeout will be used.

        :param should_stop: Optional function (returning a bool) to allow the
        waiting to be stopped before its end.

        """
        self.write("*OPC?")

        t0 = time.time()
        while True:
            try:
                ready = bool(self.read())
            except VisaIOError:
                ready = False

            if ready:
                return

            if timeout != 0 and time.time() - t0 > timeout:
                raise TimeoutError(
                    "Timeout expired while waiting for the Agilent 33220A" 
                    " to finish the triggering."
                )

            if should_stop:
                return

    def config_single_pulse_by_amp(self, amplitude: float, width: float,
                                   offset: float = 0, channel: int = 1) -> None:
        """
        Configure a square pulse. configure only the amplitude offset and width, do not change the other parameters

        :param amplitude: the pulse amplitude in V
        :param width: the pulse with in s
        :param offset: the offset
        :param channel: the channel, 1 or 2

        """

        if amplitude < 0:
            if self.polarity(channel=channel) != 'negative':
                self.set_low_amplitude(-0.001, channel=channel)
                self.set_high_amplitude(0.001, channel=channel)
                self.set_polarity('negative', channel=channel)

            self.set_low_amplitude(amplitude, channel=channel)
            self.set_high_amplitude(offset, channel=channel)

        else:
            if self.polarity(channel=channel) != 'positive':
                self.set_low_amplitude(-0.001, channel=channel)
                self.set_high_amplitude(0.001, channel=channel)
                self.set_polarity('positive', channel=channel)

            self.set_low_amplitude(0, channel=channel)
            self.set_high_amplitude(amplitude, channel=channel)
            self.set_low_amplitude(offset, channel=channel)

        if self.pulse_period(channel=channel) < width * 1.1 + 16 * NANO:
            self.set_pulse_period(width * 1.1 + 20 * NANO, channel=channel)

        self.set_pulse_width(width, channel=channel)

    def config_as_pulse_generator(self, max_amplitude=10, channel=1):
        """ set the tool as a pulse generator by loading a pulse shape wave form"""

        self.set_function('pulse', channel=channel)
        self.set_pulse_period(100 * NANO)
        self.set_pulse_edge(channel=channel)

        self.config_single_pulse_by_amp(
            amplitude=max_amplitude, width=20 * NANO, channel=channel)

        self.perform_auto_range(channel=channel)

        self.config_single_pulse_by_amp(
            amplitude=0.001, width=20 * NANO, channel=channel)

        self.set_fct_burst_state(True, channel=channel)
        self.set_fct_burst_ncycles(1, channel=channel)
        self.set_trigger_bust_mode('triggered', channel=channel)

        self.write("DISP:UNIT:VOLT HIGH")
        self.write("DISP:UNIT:RATE PER")

    def set_display(self, text) -> None:
        """
        Displays a text message on the front panel display.
        :param text: string of up to 40 ASCII keyboard characters
        :return:
        """
        self.write("DISP:TEXT \"%s\"" % text)

    def clear_display(self) -> None:
        """ Removes a text message from the display. """
        self.write("DISP:TEXT:CLE")

    def reset(self) -> None:
        """ Resets the instrument and clears the tool.  """
        self.write("ABORT")
        self.write("*RST;")
        self.write("*CLS;")
        time.sleep(1)

    def beep(self) -> None:
        """ Causes a system beep. """
        self.write("SYST:BEEP")

    def shutdown(self) -> None:
        """ Ensures that the current or voltage is turned to zero
        and disables the output. """
        for i in (1, 2):
            self.set_output(False, i)

        self.isShutdown = True
        log.info("Shutting down %s.", self.name)

    def set_sync(self, on_off: bool = False) -> None:
        """Disables or enables the front panel Sync connector"""
        cmd = 1 if on_off else 0
        self.write("OUTP:SYNC %s" % (cmd))

    def mode_sync_setup(self, mode_sync: ModeSync, channel: int = 1) -> None:
        """
        Specifies normal Sync behavior (NORMal), forces Sync to  follow the
        carrier waveform (CARRier), or indicates marker position (MARKer).
        """

        self.write("OUTP%d:SYNC:MODE %s" % (channel, mode_sync))

    def polarity_sync_setup(self, polarity_sync: PolaritySync, channel: int = 1) -> None:
        """
        Sets the desired output polarity of the Sync output to trigger external
        equipment that may require falling or rising edge triggers.
        """

        self.write("OUTP%d:SYNC:POL %s" % (channel, polarity_sync))

    def source_sync_setup(self, source_sync: SourceSync, channel: int = 1) -> None:

        """Sets the source for the Sync output connector"""

        self.write("OUTP%d:SYNC:SOUR %s" % (channel, source_sync))

    def set_cycle_burst_marker(self, cycle_marker: int, channel: int = 1) -> None:
        """
        cycle of a burst at which Sync signal goes low
        Whole number from 2 to number of cycles in the burst plus one
        (NCYCles+1), default 2
        """

        self.write("SOUR%d:MARKer:CYCle %d" % (channel, cycle_marker))

    def set_frequency_sweep_marker(self, frequency_marker: float, channel: int = 1) -> None:
        """
        Sets the marker frequency at which the front panel Sync signal goes
        low during a sweep. Any frequency between start and stop frequency,
        default 500 Hz
        """

        self.write("SOUR%d:MARKer:FREQuency %g" % (channel, frequency_marker))

    def set_point_arb_marker(self, point_marker: int, channel: int = 1) -> None:
        """
        Sets the sample number at which the front panel Sync signal goes
        low within the active arbitrary wave form. Whole number from 4 to number
        of samples in waveform, minus 3; default is midpoint of arbitrary waveform
        """

        self.write("SOUR%d:MARKer:POINt %d" % (channel, point_marker))
