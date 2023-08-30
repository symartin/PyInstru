#
# This file is part of the PyInstru package,
# parts of the code is based on the  QCoDeS package.
# parts of the code is based on the  version 0.7.0 of PyMeasure package.
#
# Copyright (c) 2013-2019 PyMeasure Developers
# Copyright (c) 2019-2023 Sylvain Martin
# Copyright (c) 2015, 2016 by Microsoft Corporation and Københavns Universitet.
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

from __future__ import annotations

import datetime as dt
import io
import logging
import struct
import time
import xml.etree.ElementTree as ET
import zipfile as zf
from typing import Any, ClassVar, Dict, Final, List, Literal, Optional, Sequence, Union

import numpy as np
import broadbean as bb
from broadbean.sequence import InvalidForgedSequenceError, fs_schema

from .. import Instrument

# Setup logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

TimeUnitType: Final = Literal['s', 'ms', 'us', 'ns']
PulseModeType: Final = Literal['externalwidth', 'quadruple', 'triple', 'double', 'single']
TriggerSourceType: Final = Literal['timer', 'external', 'manual']


class AWG70000(Instrument):
    """ Represents the Tectronix waveform generator AWG70000 generator series
    and provides a high-level interface for interacting with the instrument.
    """
    DEFAULT_SEQUENCE_PATH: ClassVar[str] = r"c:\Users\OEM\Documents\Sequences"
    DEFAULT_WAVEFORM_PATH: ClassVar[str] = r"c:\Users\OEM\Documents\Waveforms"

    def __init__(self, adapter: str, **kwargs) -> None:
        super(AWG70000, self).__init__(
            adapter, "Tectronix AWG70000", **kwargs
        )
        # The number of marker stored in each waveform included in the AWG sequence
        self._nb_marker = []

    @staticmethod
    def _is_off_str(str_or_bool):
        if str(str_or_bool).strip().capitalize() == 'OFF' \
                or (type(str_or_bool) is bool and str_or_bool is False) \
                or (type(str_or_bool) is int and str_or_bool == 0):
            return 'OFF'
        else:
            return 'ON'

    ############################################################################
    #                              System                                      #
    ############################################################################
    def current_directory(self) -> str:
        """
        This command returns the current directory of the file system on the AWG.
        The current directory for the programmatic interface is different from
        the currently selected directory in the Windows Explorer on the AWG
        """

        return self.ask("MMEMory:CDIRectory?")

    def set_current_directory(self, directory: str):
        """
        This command set the current directory of the file system on the AWG.
        The current directory for the programmatic interface is different from
        the currently selected directory in the Windows Explorer on the AWG
        """

        if len(directory) > 2 and directory[:2] == "c:":
            directory = directory[2:]
        self.write('MMEMory:CDIRectory "%s"' % directory)

    def mode(self) -> Literal["awg", "fgen"]:
        """
        This command return the AWG mode, either the AWG mode or the
        function generator mode
        """
        # noinspection PyTypeChecker
        return self.ask("INSTrument:MODE?").lower()

    def set_mode(self, mode: Literal['awg', 'fgen']):
        """
        This command sets the AWG mode, either the AWG mode or the
        function generator mode
        """
        self.write('INSTrument:MODE %s' % mode)

    def clock_sample_rate(self) -> float:
        """This command sets or returns the sample rate for the clock."""
        return float(self.ask("CLOCk:SRATe?"))

    def set_clock_sample_rate(self, sample_rate: float) -> None:
        """
        This command sets the sample rate for the clock.
        When clock_source is set to ``external``, the maximum sample rate is:
            4 * External Clock In frequency (AWG70001)
            2 * External Clock In frequency (AWG70002)

        When synchronization is enabled and the instrument is not the master,
        this command is not available

        :param sample_rate: Clock sample rate
        """
        self.write('CLOCk:SRATe %f' % sample_rate)

    def run_state(self) -> Literal['stopped', 'waiting for trigger', 'running']:
        """ This command returns the run state of the AWG """
        state = int(self.ask('AWGControl:RSTATe?').lower().strip())
        # noinspection PyTypeChecker
        return ['stopped', 'waiting for trigger', 'running'][state]

    def wait_for_operation_to_complete(self) -> None:
        """ Waits for the latest issued overlapping command to finish """
        while True:
            try:
                if int(self.ask('*OPC?')) == 1:
                    break
            except:
                pass

    def send_binary_file(self, binfile: bytes, filename: str,
                         path: str = None, overwrite: bool = True) -> None:
        """
        Send a binary file to the AWG mass memory (disk).

        :param binfile: The binary file to send.
        :param filename: The name of the file on the AWG disk, including the extension.
        :param path: The path to the directory where the file should be saved.
                     If None, use the default path ``DEFAULT_SEQUENCE_PATH``
        :param overwrite: If true, the file on disk gets overwritten
        """

        path = path or self.DEFAULT_SEQUENCE_PATH
        name_str = f'MMEMory:DATA "{filename}"'.encode('ascii')
        len_file = len(binfile)
        len_str = len(str(len_file))  # No. of digits needed to write length
        size_str = f',#{len_str}{len_file}'.encode('ascii')

        msg = name_str + size_str + binfile

        # IEEE 488.2 limit on a single write is 999,999,999 bytes
        # TODO: If this happens, we should split the file
        if len(msg) > 1e9 - 1:
            raise ValueError('File too large to transfer')

        self.set_current_directory(path)

        if overwrite:
            self.write("SYSTem:ERRor:DIALog 0")
            self.write(f'MMEMory:DELete "{filename}"')
            # if the file does not exist,
            # an error code -256 is put in the error queue
            try:
                self.ask(f'SYSTem:ERRor:CODE?')
            except:
                pass
            self.write("SYSTem:ERRor:DIALog 1")

        self.write_raw(msg)
        self.wait_for_operation_to_complete()
        # self.ask('*OPC?')
        time.sleep(0.1)

    ############################################################################
    #                             waveform                                     #
    ############################################################################
    def waveform_list(self) -> List[str]:
        """  Return the waveform list as a list of strings """
        respstr = self.ask("WLISt:LIST?")
        return respstr.strip().replace('"', '').split(',')

    def waveform_list_clear(self) -> None:
        """ Clear the waveform list """
        self.write('WLISt:WAVeform:DELete ALL')

    def new_waveform(self, waveform_name: str, size: int):
        """
        Creates a new empty waveform in the waveform list of current setup.
        :param waveform_name: the new waveform name
        :param size: number of points
        """
        self.write(f'WLIST:WAVeform:NEW "{waveform_name}", {size}')

    def waveform_set_to_channel(self, waveform_name: str, channel: int = 1) -> None:
        """
        This command assigns a waveform (from the waveform list) to the
        specified channel.

        :param waveform_name: The name of the waveform
        :param channel: the channel 1 or 2
        """
        if waveform_name not in self.waveform_list():
            raise ValueError('No such waveform in the waveform list')

        self.write('SOURce%d:CASSet:WAVeform \"%s\"' % (channel, waveform_name))

    def _import_waveform_to_wlist(self, waveform_name: str, data: bytes) -> None:
        """
        Transfers waveform data to the instrument. The waveform must be created
        using new_waveform WLISt:WAVeform:NEW.

        :param waveform_name: The name of the waveform
        :param data:  data to transfer into the waveform
        specified by waveform_name
        """

        name_str = f'WLISt:WAVeform:DATA "{waveform_name}"'.encode('ascii')
        len_data = len(data)
        nb_points = len_data / 4  # Waveform data  is stored as float, 4 bytes per float
        len_str = len(str(len_data))  # No. of digits needed to write length
        size_str = f',0,{nb_points},#{len_str}{len_data}'.encode('ascii')

        msg = name_str + size_str + data

        # IEEE 488.2 limit on a single write is 999,999,999 bytes
        # TODO: If this happens, data should be split in multiple chucnks
        if len(msg) > 1e9 - 1:
            raise ValueError('Data too large to transfer')

        self.write_raw(msg)

    def _set_waveform_marker_data(self, waveform_name: str, data: bytes) -> None:
        """
        Sets the waveform marker data

        :param waveform_name: The name of the waveform
        :param data: the marker data to transfer into the waveform specified
        by waveform_name
        """
        if waveform_name not in self.waveform_list():
            raise ValueError('No such waveform in the waveform list')

        name_str = f'WLISt:WAVeform:MARKER:DATA "{waveform_name}"'.encode('ascii')
        len_data = len(data)
        len_str = len(str(len_data))  # No. of digits needed to write length
        size_str = f',0,{len_data},#{len_str}{len_data}'.encode('ascii')

        msg = name_str + size_str + data

        # IEEE 488.2 limit on a single write is 999,999,999 bytes
        # TODO: If this happens, we should split the data
        if len(msg) > 1e9 - 1:
            raise ValueError('Data too large to transfer')

        self.write_raw(msg)

    @staticmethod
    def _make_WFMX_file_header(num_samples: int,
                               markers_included: bool) -> str:
        """
        Compiles a valid XML header for a .wfmx file
        There might be behaviour we can't capture
        We always use 9 digits for the number of header character
        """
        offsetdigits = 9

        if not isinstance(num_samples, int):
            raise ValueError('num_samples must be of type int.')

        if num_samples < 2400:
            raise ValueError('num_samples must be at least 2400.')

        # form the timestamp string
        timezone = time.timezone
        tz_m, _ = divmod(timezone, 60)  # returns (minutes, seconds)
        tz_h, tz_m = divmod(tz_m, 60)
        if np.sign(tz_h) == -1:
            signstr = '-'
            tz_h *= -1
        else:
            signstr = '+'
        timestr = dt.datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3]
        timestr += signstr
        timestr += f'{tz_h:02.0f}:{tz_m:02.0f}'

        hdr = ET.Element('DataFile', attrib={'offset': '0' * offsetdigits,
                                             'version': '0.2'})
        dsc = ET.SubElement(hdr, 'DataSetsCollection')
        dsc.set("xmlns", "http://www.tektronix.com")
        dsc.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
        dsc.set("xsi:schemaLocation", (r"http://www.tektronix.com file:///" +
                                       r"C:\Program%20Files\Tektronix\AWG70000" +
                                       r"\AWG\Schemas\awgDataSets.xsd"))
        datasets = ET.SubElement(dsc, 'DataSets')
        datasets.set('version', '1')
        datasets.set("xmlns", "http://www.tektronix.com")

        # Description of the data
        datadesc = ET.SubElement(datasets, 'DataDescription')
        temp_elem = ET.SubElement(datadesc, 'NumberSamples')
        temp_elem.text = f'{num_samples:d}'
        temp_elem = ET.SubElement(datadesc, 'SamplesType')
        temp_elem.text = 'AWGWaveformSample'
        temp_elem = ET.SubElement(datadesc, 'MarkersIncluded')
        temp_elem.text = (f'{markers_included}').lower()
        temp_elem = ET.SubElement(datadesc, 'NumberFormat')
        temp_elem.text = 'Single'
        temp_elem = ET.SubElement(datadesc, 'Endian')
        temp_elem.text = 'Little'
        temp_elem = ET.SubElement(datadesc, 'Timestamp')
        temp_elem.text = timestr

        # Product specific information
        prodspec = ET.SubElement(datasets, 'ProductSpecific')
        prodspec.set('name', 'AWG70002B')
        temp_elem = ET.SubElement(prodspec, 'RecSamplingRate')
        temp_elem.set('units', 'Hz')
        temp_elem.text = 'NaN'
        temp_elem = ET.SubElement(prodspec, 'RecAmplitude')
        temp_elem.set('units', 'Volts')
        temp_elem.text = 'NaN'
        temp_elem = ET.SubElement(prodspec, 'RecOffset')
        temp_elem.set('units', 'Volts')
        temp_elem.text = 'NaN'
        temp_elem = ET.SubElement(prodspec, 'RecFrequency')
        temp_elem.set('units', 'Hz')
        temp_elem.text = 'NaN'
        temp_elem = ET.SubElement(prodspec, 'SerialNumber')
        temp_elem.text = 'B010294'
        temp_elem = ET.SubElement(prodspec, 'SoftwareVersion')
        temp_elem.text = '7.1.0170.0'
        temp_elem = ET.SubElement(prodspec, 'UserNotes')
        # temp_elem = ET.SubElement(prodspec, 'OriginalBitDepth')
        # temp_elem.text = 'Floating'
        temp_elem = ET.SubElement(prodspec, 'Thumbnail')
        temp_elem = ET.SubElement(prodspec, 'SignalFormat')
        temp_elem.text = 'Real'
        temp_elem = ET.SubElement(prodspec, 'CreatorProperties',
                                  attrib={'name': ''})
        temp_elem = ET.SubElement(hdr, 'Setup')

        xmlstr = ET.tostring(hdr, encoding='unicode')
        xmlstr = xmlstr.replace('><', '>\r\n<')

        # As the final step, count the length of the header and write this
        # in the DataFile tag attribute 'offset'

        xmlstr = xmlstr.replace('0' * offsetdigits,
                                '{num:0{pad}d}'.format(num=len(xmlstr),
                                                       pad=offsetdigits))

        return xmlstr

    @staticmethod
    def _make_WFMX_file_binary_data(data: np.ndarray, amplitude: float) -> bytes:
        """
        For the binary part.
        Note that currently only zero markers or two markers are supported;
        one-marker data will break.

        :param data: Either a shape (N,) array with only a waveform or
        a shape (M, N) array with waveform, marker1, marker2, marker3, i.e.
        data = np.array([wfm, m1, ...]). The waveform data is assumed
        to be in V.

        :param amplitude: The peak-to-peak amplitude (V) assumed to be set on
        the channel that will play this waveform. This information is needed as
        the waveform must be rescaled to (-1, 1) where -1 will correspond to the
        channel's min. voltage and 1 to the channel's max. voltage.
        """
        channel_max = amplitude / 2
        channel_min = -amplitude / 2

        if amplitude < 0:
            channel_min = amplitude / 2
            channel_max = -amplitude / 2

        shape = np.shape(data)

        if len(shape) == 1:
            N = shape[0]
            binary_marker = b''
            wfm = data
        else:
            N = shape[1]
            M = shape[0]
            wfm = data[0, :]
            markers = data[1, :]
            for i in range(1, M - 1):
                # the 4 markers are internally encoded
                # on 4 bites 2^0, 2^1, 2^2 and 2^3 and not
                # 2^0 and 2^1 of each channel.
                # So for a sequence to work on the 2 channels,
                # the marker need to be put on 2^0 + 2^2 and
                # 2^1 + 2^3
                markers += data[i + 1, :] * (2 ** i + 2 ** (i + 2))

            markers = markers.astype(int)
            fmt = N * 'B'  # endian-ness doesn't matter for one byte
            binary_marker = struct.pack(fmt, *markers)

        if wfm.max() > channel_max or wfm.min() < channel_min:
            log.warning('Waveform exceeds specified channel range.'
                        ' The resulting waveform will be clipped. '
                        'Waveform min.: {} (V), waveform max.: {} (V),'
                        'Channel min.: {} (V), channel max.: {} (V)'
                        ''.format(wfm.min(), wfm.max(), channel_min,
                                  channel_max))

        # the data must be such that channel_max becomes 1 and
        # channel_min becomes -1
        scale = 2 / amplitude
        wfm = wfm * scale

        # TODO: Is this a fast method?
        fmt = '<' + N * 'f'
        binary_wfm = struct.pack(fmt, *wfm)
        binary_out = binary_wfm + binary_marker

        return binary_out

    def _send_waveform(self, waveform_name: str, data: np.ndarray, amplitude: float) -> None:
        """
        Compose a waveform into the instrument waveform list.
        waveform_name : The name of the waveform.

        :param data: Either a shape (N,) array with only a waveform or a shape
        (M, N) array with waveform, marker1, marker2, marker3, i.e.
        data = np.array([wfm, m1, ...]). The waveform data is assumed to be in V.

        :param amplitude: The peak-to-peak amplitude (V) assumed to be set on
        the channel that will play this waveform. This information is needed as
        the waveform must be rescaled to (-1, 1) where -1 will correspond to the
        channel's min. voltage and 1 to the channel's max. voltage.
        """
        shape = np.shape(data)

        if len(shape) == 1:
            markers_included = False
            N = shape[0]
            binary_marker = b''
            wfm = data
            self._nb_marker.append(0)
        else:
            markers_included = True
            N = shape[1]
            wfm = data[0, :]
            marker1 = data[1, :]
            marker2 = data[2, :]
            if max(marker2):
                self._nb_marker.append(2)
            else:
                self._nb_marker.append(1)
            markers = marker1 * 0b01000000 + marker2 * 0b10000000
            markers = markers.astype(int)
            fmt = N * 'B'  # endian-ness doesn't matter for one byte
            binary_marker = struct.pack(fmt, *markers)

        # Normalize the data max becomes 1 and min becomes -1
        scale = 2 / amplitude
        wfm = wfm * scale

        if max(wfm) > 1 or min(wfm) < -1:
            raise ValueError('Waveform exceeds specified channel range.')

        fmt = '<' + N * 'f'
        binary_wfm = struct.pack(fmt, *wfm)

        self.new_waveform(waveform_name, N)
        self.wait_for_operation_to_complete()
        self._import_waveform_to_wlist(waveform_name, binary_wfm)
        if markers_included: self._set_waveform_marker_data(waveform_name, binary_marker)

    @classmethod
    def make_WFMX_file(cls, data: np.ndarray, amplitude: float) -> bytes:
        """
        Compose a WFMX file

        :param data: A numpy array holding the data. Markers can be included.

        :param amplitude: The peak-to-peak amplitude (V) assumed to be set on
        the channel that will play this waveform. This information is needed as
        the waveform must be rescaled to (-1, 1) where -1 will correspond to the
        channel's min. voltage and 1 to the channel's max. voltage.
        """
        shape = np.shape(data)
        if len(shape) == 1:
            N = shape[0]
            markers_included = False
        elif len(shape) in [2, 3, 4]:
            N = shape[1]
            markers_included = True
        else:
            raise ValueError('Input data has too many dimensions!')

        wfmx_hdr_str = cls._make_WFMX_file_header(num_samples=N, markers_included=markers_included)
        wfmx = bytes(wfmx_hdr_str, 'ascii')
        wfmx += cls._make_WFMX_file_binary_data(data, amplitude)

        return wfmx

    def waveform_load_from_disk(self, filepath: str):
        """
        Loads the waveform from a .wfmx file into the Waveforms list and all
        associated (used) waveforms within the designated file in filepath
        """

        filepath = filepath.replace('\\', '\\\\')

        self.write('MMEMory:OPEN "%s"' % filepath)
        self.wait_for_operation_to_complete()

    ############################################################################
    #                            sequence                                      #
    ############################################################################
    def sequence_list(self) -> List[str]:
        """
        Return the sequence list as a list of strings
        """
        # There is no SLISt:LIST command, so we do it slightly differently
        N = int(self.ask("SLISt:SIZE?"))
        slist = []
        for n in range(1, N + 1):
            resp = self.ask(f"SLISt:NAME? {n}")
            slist.append(resp.strip().replace('"', ''))

        return slist

    def sequence_list_delete(self, seqname: str) -> None:
        """
        Delete the specified sequence from the sequence list

        :param seqname: The name of the sequence (as it appears in the sequence
        list, not the file name) to delete
        """
        self.write(f'SLISt:SEQuence:DELete "{seqname}"')

    def sequence_list_clear(self) -> None:
        """ Clear the sequence list """
        self.write('SLISt:SEQuence:DELete ALL')

    def sequence_list_new(self, seqname: str, step_number: int, track_number: int = 2):
        """
         creates a new sequence with the selected name, number of steps,
         and number of tracks
        :param seqname: the new sequence name
        :param step_number: maximum of 16383 steps and a minimum of 1
        :param track_number: 1 or 2
        """
        self.write(f'SLIST:SEQUENCE:NEW "{seqname}", {step_number}, {track_number}')

    def sequence_step_add(self, seqname: str, location: int, nb_of_step: int = 1):
        """
        This command adds steps to the named sequence.
        If the specified location is occupied, the step(s) are inserted prior to
        the specified step.

        If the specified location is the first unoccupied step in the sequence,
        the step(s) are appended to the sequence.

        If the specified location would result in a gap within the sequence,
        steps are added to bridge the gap in addition to the number of steps
        specified to add. For example, if you have a sequence with 25 steps,
        and you specify to add 5 steps beginning at location 30, steps will be
        added to fill the gap between steps 25 and 30

        :param seqname: the sequence name
        :param location:  location to add/insert the step(s)
        :param nb_of_step: number of steps to add

        """
        self.write(f'SLIST:SEQUENCE:STEP:ADD "{seqname}", {location}, {nb_of_step}')

    def sequence_set_step_waveform(self, sequence_name: str,
                                   step: int, waveform_name: str, track: int):
        """
        This command assigns a wavefoirm for a specific sequence's step and track.
        This waveform is played whenever the playing sequence reaches this step.

        :param sequence_name: the sequence name
        :param step:  value specifying a sequence step
        :param waveform_name: the waveform to assign
        :param track: value specifying the track in a sequence

        """
        self.write(f'SLIST:SEQUENCE:STEP{step}:TASSET{track}:WAVEFORM '
                   + f'"{sequence_name}", {waveform_name}')

    def sequence_set_step_jump(
            self, seqname: str, step: int,
            trigger: Literal['a', 'b', 'internal', 'off'],
            destination: Union[int, Literal['last', 'first', 'next', 'end']] = 'next'):
        """
        This command sets wether the sequence will jump when it receives
        Trigger A, Trigger B, Internal Trigger, and where it will jump or no
        jump at all. This is settable for every step in a sequence.

        ============ ========================================================================
        destination  description
        ============ ========================================================================
        next         This enables the sequencer to jump to the next sequence step.
        first        This enables the sequencer to jump to first step in the sequence.
        last         This enables the sequencer to jump to the last step in the sequence.
        end          This enables the sequencer to jump to the end and play 0V
        an int       This give the step number in int
        ============ ========================================================================

        :param seqname: the sequence name
        :param step:  value specifying a sequence step
        :param trigger: the triger type
        :param destination: the destination step

        """
        trigger_dict = {'a': 'ATRIGGER', 'b': 'BTRIGGER', 'internal': 'ITRIGGER', 'off': 'OFF'}

        trigger = trigger_dict[trigger.lower()]
        self.write(f'SLIST:SEQUENCE:STEP{step}:EJINPUT "{seqname}", {trigger}')
        if trigger != 'OFF':
            self.write(f'SLIST:SEQUENCE:STEP{step}:EJUMP "{seqname}", {destination}')

    def sequence_set_step_rcount(self, seqname: str, step: int,
                                 count: Union[str, int]):
        """
        This command sets the repeat count, which is the number of times the
        assigned waveform play before proceeding to the next step in the sequence

        :param seqname: the sequence name

        :param step:  value specifying a sequence step

        :param count: number of repetition, Infinite stands for repeat count to
        Infinite, indicating that a waveform in track will play until stopped
        externally by the AWGControl:STOP command or SLISt:SEQ:JUMP:IMMediate
        command.
        """
        if isinstance(count, int):
            if count <= 0:
                raise ValueError('Repeat count is less than minimum : 1')
            elif count > 1048576:
                raise ValueError('Repeat count is exceeding maximum : 2^20')
        self.write(f'SLISt:SEQuence:STEP{step}:RCOunt "{seqname}", {count}')

    def sequence_query_step_rcount(self, seqname: str, step: int) -> Union[str, int]:
        """
        This command queries the repeat count, which is the number of times the
        assigned waveform play before proceeding to the next step in the sequence

        :param seqname: the sequence name
        :param step:  value specifying a sequence step

        return: number of repetition
        """

        return self.ask(f'SLISt:SEQuence:STEP{step}:RCOunt? "{seqname}"')

    def sequence_set_to_channel(self, seqname: str, track_nb: int,
                                channel: int = 1) -> None:
        """
        Assign a track from a sequence to this channel.

        :param seqname: Name of the sequence in the sequence list
        :param track_nb: Which track to use (1 or 2)
        :param channel: the channel 1 or 2
        """
        self.write(f'SOURCE{channel}:CASSet:SEQuence "{seqname}", {track_nb}')

    def sequence_list_amplitude(self, seqname: str) -> float:
        """
        Sets the recommended amplitude (peak-to-peak) of the specified sequence.
        """
        return float(self.ask(f'SLIST:SEQUENCE:AMPLITUDE "{seqname}"'))

    def sequence_set_list_amplitude(self, seqname: str, amplitude: float):
        """
        Returns the recommended amplitude peak-to-peak of the specified sequence.
        """
        self.write(f'SLIST:SEQUENCE:AMPLITUDE "{seqname}", {amplitude}')

    def sequence_load_from_disk(self, filepath: str):
        """ This command loads  all the sequence from a seqx file
        into the Sequences list and all associated (used) sequences
        and waveforms within  the designated file in filepath."""
        filepath = filepath.replace('\\', '\\\\')

        self.write('MMEMory:OPEN:SASSet:SEQuence "%s"' % filepath)
        self.wait_for_operation_to_complete()

    @classmethod
    def make_SEQX_from_forged_sequence(
            cls,
            seq: Dict[int, Dict[Any, Any]],
            amplitudes: List[float],
            seqname: str,
            channel_mapping: Optional[Dict[Union[str, int], int]] = None) -> bytes:
        """
        Make a .seqx from a forged broadbean sequence. Supports subsequences.

        :param seq: The output of broadbean's Sequence.forge()

        :param amplitudes: A list of the AWG channels' voltage amplitudes.
        The first entry is ch1 etc.

        :param channel_mapping: A mapping from what the channel is called
        in the broadbean sequence to the integer describing the physical channel
        it should be assigned to.

        :param seqname: The name that the sequence will have in the AWG's
        sequence list. Used for loading the sequence.

        :returns: The binary .seqx file contents. Can be sent directly to the
        instrument or saved on disk.
        """

        try:
            fs_schema.validate(seq)
        except Exception as e:
            raise InvalidForgedSequenceError(e)

        chan_list: List[Union[str, int]] = []
        for pos1 in seq.keys():
            for pos2 in seq[pos1]['content'].keys():
                for ch in seq[pos1]['content'][pos2]['data'].keys():
                    if ch not in chan_list:
                        chan_list.append(ch)

        if channel_mapping is None:
            channel_mapping = {ch: ch_ind + 1
                               for ch_ind, ch in enumerate(chan_list)}

        if len(set(chan_list)) != len(amplitudes):
            raise ValueError('Incorrect number of amplitudes provided.')

        if set(chan_list) != set(channel_mapping.keys()):
            raise ValueError(f'Invalid channel_mapping. The sequence has '
                             f'channels {set(chan_list)}, but the '
                             'channel_mapping maps from the channels '
                             f'{set(channel_mapping.keys())}')

        if set(channel_mapping.values()) != set(range(1, 1 + len(chan_list))):
            raise ValueError('Invalid channel_mapping. Must map onto '
                             f'{list(range(1, 1 + len(chan_list)))}')

        ##########
        # STEP 1:
        # Make all .wfmx files

        wfmx_files: List[bytes] = []
        wfmx_filenames: List[str] = []

        for pos1 in seq.keys():
            for pos2 in seq[pos1]['content'].keys():
                for ch, data in seq[pos1]['content'][pos2]['data'].items():
                    wfm = data['wfm']

                    markerdata = []
                    for mkey in ['m1', 'm2', 'm3', 'm4']:
                        if mkey in data.keys():
                            markerdata.append(data.get(mkey))

                    if len(markerdata) > 0:
                        wfm_data = np.stack((wfm, *markerdata))
                    else:
                        wfm_data = wfm

                    awgchan = channel_mapping[ch]
                    wfmx = cls.make_WFMX_file(wfm_data, amplitudes[awgchan - 1])
                    wfmx_files.append(wfmx)
                    wfmx_filenames.append(f'wfm_{pos1}_{pos2}_{awgchan}')

        ##########
        # STEP 2:
        # Make all subsequence .sml files

        subseqsml_files: List[str] = []
        subseqsml_filenames: List[str] = []

        for pos1 in seq.keys():
            if seq[pos1]['type'] == 'subsequence':

                ss_wfm_names: List[List[str]] = []

                # we need to "flatten" all the individual dicts of element
                # sequence options into one dict of lists of sequencing options
                # and we must also provide default values if nothing
                # is specified
                seqings: List[Dict[str, int]] = []
                for pos2 in (seq[pos1]['content'].keys()):
                    pos_seqs = seq[pos1]['content'][pos2]['sequencing']
                    pos_seqs['twait'] = pos_seqs.get('twait', 0)
                    pos_seqs['nrep'] = pos_seqs.get('nrep', 1)
                    pos_seqs['jump_input'] = pos_seqs.get('jump_input', 0)
                    pos_seqs['jump_target'] = pos_seqs.get('jump_target', 0)
                    pos_seqs['goto'] = pos_seqs.get('goto', 0)
                    seqings.append(pos_seqs)

                    ss_wfm_names.append([n for n in wfmx_filenames
                                         if f'wfm_{pos1}_{pos2}' in n])

                seqing = {k: [d[k] for d in seqings]
                          for k in seqings[0].keys()}

                subseqname = f'subsequence_{pos1}'

                log.debug(f'Subsequence waveform names: {ss_wfm_names}')

                subseqsml = cls._make_SML_file(trig_waits=seqing['twait'],
                                               nreps=seqing['nrep'],
                                               event_jumps=seqing['jump_input'],
                                               event_jump_to=seqing['jump_target'],
                                               go_to=seqing['goto'],
                                               elem_names=ss_wfm_names,
                                               seqname=subseqname,
                                               chans=len(channel_mapping))

                subseqsml_files.append(subseqsml)
                subseqsml_filenames.append(f'{subseqname}')

        ##########
        # STEP 3:
        # Make the main .sml file

        asset_names: List[List[str]] = []
        seqings = []
        subseq_positions: List[int] = []
        for pos1 in seq.keys():
            pos_seqs = seq[pos1]['sequencing']

            pos_seqs['twait'] = pos_seqs.get('twait', 0)
            pos_seqs['nrep'] = pos_seqs.get('nrep', 1)
            pos_seqs['jump_input'] = pos_seqs.get('jump_input', 0)
            pos_seqs['jump_target'] = pos_seqs.get('jump_target', 0)
            pos_seqs['goto'] = pos_seqs.get('goto', 0)
            seqings.append(pos_seqs)
            if seq[pos1]['type'] == 'subsequence':
                subseq_positions.append(pos1)
                asset_names.append([sn for sn in subseqsml_filenames
                                    if f'_{pos1}' in sn])
            else:
                asset_names.append([wn for wn in wfmx_filenames
                                    if f'wfm_{pos1}' in wn])
        seqing = {k: [d[k] for d in seqings] for k in seqings[0].keys()}

        log.debug(f'Assets for SML file: {asset_names}')

        mainseqname = seqname
        mainseqsml = cls._make_SML_file(trig_waits=seqing['twait'],
                                        nreps=seqing['nrep'],
                                        event_jumps=seqing['jump_input'],
                                        event_jump_to=seqing['jump_target'],
                                        go_to=seqing['goto'],
                                        elem_names=asset_names,
                                        seqname=mainseqname,
                                        chans=len(channel_mapping),
                                        subseq_positions=subseq_positions)

        ##########
        # STEP 4:
        # Build the .seqx file

        user_file = b''
        setup_file = cls._make_setup_file(mainseqname)

        buffer = io.BytesIO()

        zipfile = zf.ZipFile(buffer, mode='a')
        for ssn, ssf in zip(subseqsml_filenames, subseqsml_files):
            zipfile.writestr(f'Sequences/{ssn}.sml', ssf)
        zipfile.writestr(f'Sequences/{mainseqname}.sml', mainseqsml)

        for (name, wfile) in zip(wfmx_filenames, wfmx_files):
            zipfile.writestr(f'Waveforms/{name}.wfmx', wfile)

        zipfile.writestr('setup.xml', setup_file)
        zipfile.writestr('userNotes.txt', user_file)
        zipfile.close()

        buffer.seek(0)
        seqx = buffer.getvalue()
        buffer.close()

        return seqx

    def load_broadbean_sequence(
            self,
            seq: bb.Sequence(),
            seqname: str,
            channel_mapping: Optional[Dict[Union[str, int], int]] = None,
            amplitudes: Optional[List[float]] = None,
            resolution: Optional[Literal[8, 9, 10]] = None,
            output: Optional[bool] = False) -> None:
        """
        Creates and import a sequence in the instrument sequence list from a
        broadbean sequence. Does not support subsequences.

        :param seq: a broadbean sequence

        :param seqname: The name that the sequence will have in the AWG's
                sequence list. Used for loading the sequence.

        :param channel_mapping: A mapping from what the channel is called
        in the broadbean sequence to the integer describing the physical channel
        it should be assigned to.

        :param amplitudes: A list of the AWG channels' voltage  amplitudes.
        The first entry is ch1 etc. If not specify set the channels to the
        maximum amplitude : 0.5V

        :param resolution: Resolution in bit of the DAC, if not specified,
        autoset the resolution to the max available depending on the number
        of marker in use.

        :param output: If true, apply the sequence to the channels, set the DAC
        resolution, enable the ouput and play the sequence.

        :returns: The binary .seqx file contents. Can be sent directly to the
         instrument or saved on disk.
        """
        self._nb_marker = []
        forged_seq = seq.forge()
        try:
            fs_schema.validate(forged_seq)
        except Exception as e:
            raise InvalidForgedSequenceError(e)

        chan_list: List[Union[str, int]] = []
        for pos1 in forged_seq.keys():
            for pos2 in forged_seq[pos1]['content'].keys():
                for ch in forged_seq[pos1]['content'][pos2]['data'].keys():
                    if ch not in chan_list:
                        chan_list.append(ch)

        if amplitudes is None:  # Set amplitude default to max amplitude
            amplitudes = [0.5] * len(chan_list)

        if channel_mapping is None:
            channel_mapping = {ch: ch_ind + 1
                               for ch_ind, ch in enumerate(chan_list)}

        if len(set(chan_list)) != len(amplitudes):
            raise ValueError('Incorrect number of amplitudes provided.')

        if set(chan_list) != set(channel_mapping.keys()):
            raise ValueError(f'Invalid channel_mapping. The sequence has '
                             f'channels {set(chan_list)}, but the '
                             'channel_mapping maps from the channels '
                             f'{set(channel_mapping.keys())}')

        if set(channel_mapping.values()) != set(range(1, 1 + len(chan_list))):
            raise ValueError('Invalid channel_mapping. Must map onto '
                             f'{list(range(1, 1 + len(chan_list)))}')

        # Make waveforms element
        waveform_names: List[str] = []

        for pos1 in forged_seq.keys():
            for pos2 in forged_seq[pos1]['content'].keys():
                for ch, data in forged_seq[pos1]['content'][pos2]['data'].items():
                    awgchan = channel_mapping[ch]
                    wfm = data['wfm']
                    waveform_name = f'wfm_{pos1}_{pos2}_{awgchan}'
                    marker_data = []
                    for mkey in ['m1', 'm2', 'm3', 'm4']:
                        if mkey in data.keys():
                            marker_data.append(data.get(mkey))
                    if len(marker_data) > 0:
                        wfm_data = np.stack((wfm, *marker_data))
                    else:
                        wfm_data = wfm
                    self._send_waveform(waveform_name, wfm_data, amplitudes[awgchan - 1])
                    waveform_names.append(waveform_name)

        # Make the sequence
        asset_names: List[List[str]] = []
        seqings = []
        for pos1 in forged_seq.keys():
            pos_seqs = forged_seq[pos1]['sequencing']

            pos_seqs['twait'] = pos_seqs.get('twait', 0)
            pos_seqs['nrep'] = pos_seqs.get('nrep', 1)
            pos_seqs['jump_input'] = pos_seqs.get('jump_input', 0)
            pos_seqs['jump_target'] = pos_seqs.get('jump_target', 0)
            pos_seqs['goto'] = pos_seqs.get('goto', 0)
            seqings.append(pos_seqs)
            if forged_seq[pos1]['type'] == 'subsequence':
                raise ValueError('Subsequence are not supported')
            else:
                asset_names.append([wn for wn in waveform_names
                                    if wn.split("_")[1] == str(pos1)])
        seqing = {k: [d[k] for d in seqings] for k in seqings[0].keys()}

        log.debug(f'Assets for sequence: {asset_names}')

        self._send_sequence(
            trig_waits=seqing['twait'],
            nreps=seqing['nrep'],
            event_jumps=seqing['jump_input'],
            event_jump_to=seqing['jump_target'],
            go_to=seqing['goto'],
            elem_names=asset_names,
            seqname=seqname,
            chans=len(channel_mapping)
        )
        if output:
            for channel in chan_list:
                max_resolution = 10 - max(self._nb_marker)
                if resolution is None:
                    resolution = max_resolution
                elif resolution > max_resolution:
                    raise ValueError('Specified resolution exceed the maximum')
                self.set_output_resolution(resolution, channel)
                self.sequence_set_to_channel(R'%s' % seqname, channel, channel)
                for amplitude in amplitudes:
                    self.set_amplitude(amplitude, channel)
                self.enable(channel)
            self.play(wait_for_running=False)
            self.wait_for_operation_to_complete()

    @classmethod
    def make_SEQX_file(cls,
                       trig_waits: Sequence[int], nreps: Sequence[int],
                       event_jumps: Sequence[int], event_jump_to: Sequence[int],
                       go_to: Sequence[int], wfms: Sequence[Sequence[np.ndarray]],
                       amplitudes: Sequence[float], seqname: str) -> bytes:
        """
        Make a full .seqx file (bundle)

        A .seqx file can presumably hold several sequences, but for now
        we support only packing a single sequence
        For a single sequence, a .seqx file is a bundle of two files and
        two folders:
        /Sequences
            sequence.sml
        /Waveforms
            wfm1.wfmx
            wfm2.wfmx
            ...
        setup.xml
        userNotes.txt

        :param trig_waits: Wait for a trigger? If yes, you must specify the
        trigger input. 0 for off, 1 for 'TrigA', 2 for 'TrigB', 3 for 'Internal'.

        :param nreps: No. of repetitions. 0 corresponds to infinite.

        :param event_jumps: Jump when event triggered? If yes, you must specify
        the trigger input. 0 for off, 1 for 'TrigA', 2 for 'TrigB',
        3 for 'Internal'.

        :param event_jump_to: Jump target in case of event. 1-indexed,
        0 means next. Must be specified for all elements.

        :param go_to: Which element to play next. 1-indexed, 0 means next.

        :param wfms: numpy arrays describing each waveform plus two markers,
        packed like np.array([wfm, m1, m2]). These numpy arrays are then again
        packed in lists according to:
            [[wfmch1pos1, wfmch1pos2, ...], [wfmch2pos1, ...], ...]

        :param amplitudes: The peak-to-peak amplitude in V of the channels, i.e.
        a list [ch1_amp, ch2_amp].

        :param seqname: The name of the sequence. This name will appear in the
        sequence list. Note that all spaces are converted to '_'

        :returns: The binary .seqx file, ready to be sent to the instrument.
        """

        # input sanitising to avoid spaces in filenames
        seqname = seqname.replace(' ', '_')

        (chans, elms) = (len(wfms), len(wfms[0]))
        wfm_names = [[f'wfmch{ch}pos{el}' for ch in range(1, chans + 1)]
                     for el in range(1, elms + 1)]

        # generate wfmx files for the waveforms
        flat_wfmxs = []  # type: list[bytes]
        for amplitude, wfm_lst in zip(amplitudes, wfms):
            flat_wfmxs += [cls.make_WFMX_file(wfm, amplitude)
                           for wfm in wfm_lst]

        # This unfortunately assumes no subsequences
        flat_wfm_names = list(np.reshape(np.array(wfm_names).transpose(),
                                         (chans * elms,)))

        sml_file = cls._make_SML_file(trig_waits, nreps,
                                      event_jumps, event_jump_to,
                                      go_to, wfm_names,
                                      seqname,
                                      chans)

        user_file = b''
        setup_file = cls._make_setup_file(seqname)

        buffer = io.BytesIO()

        zipfile = zf.ZipFile(buffer, mode='a')
        zipfile.writestr(f'Sequences/{seqname}.sml', sml_file)

        for (name, wfile) in zip(flat_wfm_names, flat_wfmxs):
            zipfile.writestr(f'Waveforms/{name}.wfmx', wfile)

        zipfile.writestr('setup.xml', setup_file)
        zipfile.writestr('userNotes.txt', user_file)
        zipfile.close()

        buffer.seek(0)
        seqx = buffer.getvalue()
        buffer.close()

        return seqx

    @staticmethod
    def _make_setup_file(sequence: str) -> str:
        """
        Make a setup.xml file.

        :param sequence: The name of the main sequence

        :returns: The setup file as a string
        """
        head = ET.Element('RSAPersist')
        head.set('version', '0.1')
        temp_elem = ET.SubElement(head, 'Application')
        temp_elem.text = 'Pascal'
        temp_elem = ET.SubElement(head, 'MainSequence')
        temp_elem.text = sequence
        prodspec = ET.SubElement(head, 'ProductSpecific')
        prodspec.set('name', 'AWG70002B')
        temp_elem = ET.SubElement(prodspec, 'SerialNumber')
        temp_elem.text = 'B010294'
        temp_elem = ET.SubElement(prodspec, 'SoftwareVersion')
        temp_elem.text = '7.1.0170.0'
        temp_elem = ET.SubElement(prodspec, 'CreatorProperties')
        temp_elem.set('name', '')

        xmlstr = ET.tostring(head, encoding='unicode')
        xmlstr = xmlstr.replace('><', '>\r\n<')

        return xmlstr

    @staticmethod
    def _make_SML_file(trig_waits: Sequence[int], nreps: Sequence[int],
                       event_jumps: Sequence[int], event_jump_to: Sequence[int],
                       go_to: Sequence[int], elem_names: Sequence[Sequence[str]],
                       seqname: str, chans: int,
                       subseq_positions: Sequence[int] = ()) -> str:
        """
        Make an xml file describing a sequence.

        :param trig_waits: Wait for a trigger? If yes, you must specify the
        trigger input. 0 for off, 1 for 'TrigA', 2 for 'TrigB',  3 for 'Internal'.

        :param nreps: No. of repetitions. 0 corresponds to infinite.

        :param event_jumps: Jump when event triggered? If yes, you must specify
        the trigger input. 0 for off, 1 for 'TrigA', 2 for 'TrigB', 3 for 'Internal'.

        :param event_jump_to: Jump target in case of event. 1-indexed,
        0 means next. Must be specified for all elements.

        :param go_to: Which element to play next. 1-indexed, 0 means next.

        :param elem_names: The waveforms/subsequences to use. Should be packed
        like:
        [[wfmpos1ch1, wfmpos1ch2, ...],
         [subseqpos2],
         [wfmpos3ch1, wfmpos3ch2, ...], ...]

        :param seqname: The name of the sequence. This name will appear in
        the sequence list of the instrument.

        :param chans: The number of channels. Can not be inferred in the case
        of a sequence containing only subsequences, so must be provided up front.

        :paramsubseq_positions: The positions (step numbers) occupied by subsequences

        :returns: A str containing the file contents, to be saved as an .sml file
        """

        offsetdigits = 9

        waitinputs = {0: 'None', 1: 'TrigA', 2: 'TrigB', 3: 'Internal'}
        eventinputs = {0: 'None', 1: 'TrigA', 2: 'TrigB', 3: 'Internal'}

        inputlsts = [trig_waits, nreps, event_jump_to, go_to]
        lstlens = [len(lst) for lst in inputlsts]
        if lstlens.count(lstlens[0]) != len(lstlens):
            raise ValueError('All input lists must have the same length!')

        if lstlens[0] == 0:
            raise ValueError('Received empty sequence option lengths!')

        if lstlens[0] != len(elem_names):
            raise ValueError('Mismatch between number of waveforms and'
                             ' number of sequencing steps.')

        N = lstlens[0]

        # form the timestamp string
        timezone = time.timezone
        tz_m, _ = divmod(timezone, 60)
        tz_h, tz_m = divmod(tz_m, 60)
        if np.sign(tz_h) == -1:
            signstr = '-'
            tz_h *= -1
        else:
            signstr = '+'
        timestr = dt.datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3]
        timestr += signstr
        timestr += f'{tz_h:02.0f}:{tz_m:02.0f}'

        datafile = ET.Element('DataFile', attrib={'offset': '0' * offsetdigits,
                                                  'version': '0.1'})
        dsc = ET.SubElement(datafile, 'DataSetsCollection')
        dsc.set("xmlns", "http://www.tektronix.com")
        dsc.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
        dsc.set("xsi:schemaLocation", (r"http://www.tektronix.com file:///" +
                                       r"C:\Program%20Files\Tektronix\AWG70000" +
                                       r"\AWG\Schemas\awgSeqDataSets.xsd"))
        datasets = ET.SubElement(dsc, 'DataSets')
        datasets.set('version', '1')
        datasets.set("xmlns", "http://www.tektronix.com")

        # Description of the data
        datadesc = ET.SubElement(datasets, 'DataDescription')
        temp_elem = ET.SubElement(datadesc, 'SequenceName')
        temp_elem.text = seqname
        temp_elem = ET.SubElement(datadesc, 'Timestamp')
        temp_elem.text = timestr
        temp_elem = ET.SubElement(datadesc, 'JumpTiming')
        temp_elem.text = 'JumpImmed'  # TODO: What does this control?
        temp_elem = ET.SubElement(datadesc, 'RecSampleRate')
        temp_elem.text = 'NaN'
        temp_elem = ET.SubElement(datadesc, 'RepeatFlag')
        temp_elem.text = 'false'
        temp_elem = ET.SubElement(datadesc, 'PatternJumpTable')
        temp_elem.set('Enabled', 'false')
        temp_elem.set('Count', '256')
        steps = ET.SubElement(datadesc, 'Steps')
        steps.set('StepCount', f'{N:d}')
        steps.set('TrackCount', f'{chans:d}')

        for n in range(1, N + 1):
            step = ET.SubElement(steps, 'Step')
            temp_elem = ET.SubElement(step, 'StepNumber')
            temp_elem.text = f'{n:d}'
            # repetitions
            rep = ET.SubElement(step, 'Repeat')
            repcount = ET.SubElement(step, 'RepeatCount')
            if nreps[n - 1] == 0:
                rep.text = 'Infinite'
                repcount.text = '1'
            elif nreps[n - 1] == 1:
                rep.text = 'Once'
                repcount.text = '1'
            else:
                rep.text = "RepeatCount"
                repcount.text = f"{nreps[n - 1]:d}"
            # trigger wait
            temp_elem = ET.SubElement(step, 'WaitInput')
            temp_elem.text = waitinputs[trig_waits[n - 1]]
            # event jump
            temp_elem = ET.SubElement(step, 'EventJumpInput')
            temp_elem.text = eventinputs[event_jumps[n - 1]]
            jumpto = ET.SubElement(step, 'EventJumpTo')
            jumpstep = ET.SubElement(step, 'EventJumpToStep')
            if event_jump_to[n - 1] == 0:
                jumpto.text = 'Next'
                jumpstep.text = '1'
            else:
                jumpto.text = "StepIndex"
                jumpstep.text = f"{event_jump_to[n - 1]:d}"
            # Go to
            goto = ET.SubElement(step, 'GoTo')
            gotostep = ET.SubElement(step, 'GoToStep')
            if go_to[n - 1] == 0:
                goto.text = 'Next'
                gotostep.text = '1'
            else:
                goto.text = "StepIndex"
                gotostep.text = f"{go_to[n - 1]:d}"

            assets = ET.SubElement(step, 'Assets')
            for assetname in elem_names[n - 1]:
                asset = ET.SubElement(assets, 'Asset')
                temp_elem = ET.SubElement(asset, 'AssetName')
                temp_elem.text = assetname
                temp_elem = ET.SubElement(asset, 'AssetType')
                if n in subseq_positions:
                    temp_elem.text = 'Sequence'
                else:
                    temp_elem.text = 'Waveform'

            flags = ET.SubElement(step, 'Flags')
            for _ in range(chans):
                flagset = ET.SubElement(flags, 'FlagSet')
                for flg in ['A', 'B', 'C', 'D']:
                    temp_elem = ET.SubElement(flagset, 'Flag')
                    temp_elem.set('name', flg)
                    temp_elem.text = 'NoChange'

        temp_elem = ET.SubElement(datasets, 'ProductSpecific')
        temp_elem.set('name', '')
        temp_elem = ET.SubElement(datafile, 'Setup')

        # the tostring() call takes roughly 75% of the total
        # time spent in this function. Can we speed up things?
        # perhaps we should use lxml?
        xmlstr = ET.tostring(datafile, encoding='unicode')
        xmlstr = xmlstr.replace('><', '>\r\n<')

        # As the final step, count the length of the header and write this
        # in the DataFile tag attribute 'offset'

        xmlstr = xmlstr.replace('0' * offsetdigits,
                                '{num:0{pad}d}'.format(num=len(xmlstr),
                                                       pad=offsetdigits))

        return xmlstr

    def _send_sequence(self, trig_waits: Sequence[int], nreps: Sequence[int],
                       event_jumps: Sequence[int], event_jump_to: Sequence[int],
                       go_to: Sequence[int], elem_names: Sequence[Sequence[str]],
                       seqname: str, chans: int) -> None:
        """
        Creates a sequence made of arbitrary waveforms (or subsequence, code not
        validated yet) and has the generator output them sequentially.
        Each element of the argument array pertains to the sequence waveform
        of that index.


        :param trig_waits: Wait for a trigger? If yes, you must specify the
        trigger input. 0 for off, 1 for 'TrigA', 2 for 'TrigB',
        3 for 'Internal'.

        :param nreps: No. of repetitions. 0 corresponds to infinite.
        event_jumps: Jump when event triggered? If yes, you must specify
        the trigger input. 0 for off, 1 for 'TrigA', 2 for 'TrigB',
        3 for 'Internal'.

        :param event_jump_to: Jump target in case of event. 1-indexed,
        0 means next. Must be specified for all elements.

        :param go_to: Which element to play next. 1-indexed, 0 means next.

        :param elem_names: The waveforms to use. Should be packed
        like:
        [[wfmpos1ch1, wfmpos1ch2, ...],
         [wfmpos2ch1, wfmpos2ch2, ...], ...]
         subsequences are not supported

        :param seqname: The name of the sequence. This name will appear in
        the sequence list of the instrument.

        :param chans: The number of channels. Can not be inferred in the case
        of a sequence containing only subsequences, so must be provided
        up front.
        """
        waitinputs = {0: 'OFF', 1: 'ATR', 2: 'BTR', 3: 'ATR'}
        eventinputs = {0: 'OFF', 1: 'ATR', 2: 'BTR', 3: 'ATR'}

        inputlsts = [trig_waits, nreps, event_jump_to, go_to]
        lstlens = [len(lst) for lst in inputlsts]
        if lstlens.count(lstlens[0]) != len(lstlens):
            raise ValueError('All input lists must have the same length!')

        if lstlens[0] == 0:
            raise ValueError('Received empty sequence option lengths!')

        if lstlens[0] != len(elem_names):
            raise ValueError('Mismatch between number of waveforms and'
                             ' number of sequencing steps.')

        N = lstlens[0]

        # Create the sequence
        command_stack = f':SLIS:SEQ:NEW "{seqname}", {N}, {chans};'

        for n in range(1, N + 1):
            # Configure repetition count
            if nreps[n - 1] == 0:
                command_stack += f':SLIS:SEQ:STEP{n}:RCO "{seqname}",Infinite;'
            elif nreps[n - 1] != 1:
                command_stack += f':SLIS:SEQ:STEP{n}:RCO "{seqname}",{nreps[n - 1]:d};'
            # trigger wait
            if waitinputs[trig_waits[n - 1]] != 'OFF':
                # The method is not used to modify the sequence, then no need to
                # send a command to set to 'OFF' since its the default value
                command_stack += f':SLIS:SEQ:STEP{n}:WINPUT "{seqname}",{waitinputs[trig_waits[n - 1]]};'
            # event jump
            if eventinputs[event_jumps[n - 1]] != 'OFF':
                command_stack += f':SLIS:SEQ:STEP{n}:EJIN "{seqname}",{eventinputs[event_jumps[n - 1]]};'
                if event_jump_to[n - 1] == 0:
                    jumpto = 'Next'
                else:
                    jumpto = f"{event_jump_to[n - 1]:d}"
                command_stack += f':SLIS:SEQ:STEP{n}:EJUMP "{seqname}",{jumpto};'

            # Go to
            if go_to[n - 1] != 0:
                goto = f"{go_to[n - 1]:d}"
                command_stack += f':SLIS:SEQ:STEP{n}:GOTO "{seqname}",{goto};'

            for assetname in elem_names[n - 1]:
                track = assetname.split('_')[3]
                command_stack += f':SLIS:SEQ:STEP{n}:TASS{track}:WAV "{seqname}","{assetname}";'

        self.write(command_stack)

    ############################################################################
    #                        output configuration                              #
    ############################################################################
    def set_output_resolution(self, resolution_bit: Literal[8, 9, 10], channel: int = 1):
        """ This command sets or returns the DAC resolution.

        resolution_bit:
            8 indicates 8 bit DAC Resolution + 2 marker bits.
            9 indicates 9 bit DAC Resolution + 1 marker bit.
            10 indicates 10 bit DAC Resolution + 0 marker bits

        :param resolution_bit: the DAC resolution
        :param channel: the channel 1 or 2
        """
        self.write("SOURce%d:DAC:RESolution %d" % (channel, resolution_bit))

    def output_resolution(self, channel: int = 1):
        """ This command sets or returns the DAC resolution.

        resolution_bit:
            8 indicates 8 bit DAC Resolution + 2 marker bits.
            9 indicates 9 bit DAC Resolution + 1 marker bit.
            10 indicates 10 bit DAC Resolution + 0 marker bits

        :param channel: the channel 1 or 2
        """
        return int(float(self.ask("SOURce%d:DAC:RESolution?" % channel)))

    def set_output_amplitude(self, amplitude: float, channel: int):
        """ This command sets the function generator’s waveform amplitude value
            for the specified channel in units of volts.

            :param amplitude: teh amplitude in volts
            :param channel: the channel 1 or 2
        """

        if self.mode() == "awg":
            if amplitude > 0.5:
                raise ValueError('Specified amplitude exceed the maximum')
            self.write("SOURCE%d:VOLTAGE %g" % (channel, amplitude))
        else:
            self.write("FGEN:CHANNEL%d:AMPLITUDE %g" % (channel, amplitude))

    def output_amplitude(self, channel: int) -> float:
        """ This command return the function generator’s waveform amplitude value
            for the specified channel in units of volts.

            :param channel: the channel 1 or 2
        """

        if self.mode() == "awg":
            return float(self.write("SOURCE%d:VOLTAGE?" % (channel)))
        else:
            return float(self.write("FGEN:CHANNEL%d:AMPLITUDE?" % channel))

    def set_output(self, on_off: bool = False, channel: int = 1) -> None:
        """
        This command enables or disables a channel of the pulse generator.

        :param on_off: boolean True : enable, False : disables
        :param channel: the output channel int from 1 to 2
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

    def amplitude(self, channel: int = 1) -> float:
        """
        This command queries the output amplitude for the specified output channel.
        :param channel: the output channel int from 1 to 2
        :return: the amplitude in V
        """
        return float(self.ask("SOUR%d:VOLT:AMPL?" % channel))

    def set_amplitude(self, amplitude, channel: int = 1) -> None:
        """
        This command sets the output amplitude for the specified output channel.
        :param amplitude: the amplitude in V peak to peak
        :param channel: the output channel int from 1 to 2
        :return: None
        """
        if amplitude > 0.5:
            raise ValueError('Specified amplitude exceed the maximum')
        self.write("SOUR%d:VOLT:AMPL %g" % (channel, amplitude))

    def offset(self, channel: int = 1) -> float:
        """
        This command queries the offset voltage for the specified
        output channel.

        :param channel: the output channel int from 1 to 2
        :return: the offset in V
        """
        return float(self.ask("SOUR%d:VOLT:LEV:IMM:OFFS?" % channel))

    def set_offset(self, offset, channel: int = 1) -> None:
        """
        This command sets the offset voltage for the specified
        output channel.

        :param offset: the offset in V
        :param channel: the output channel int from 1 to 2
        :return: None
        """
        self.write("SOUR%d:VOLT:LEV:IMM:OFFS %g" % (channel, offset))

    def low_amplitude(self, channel: int = 1) -> float:
        """
        This command queries the low level of the output amplitude
        for the specified channel

        :param channel: the output channel int from 1 to 2
        :return: The amplitude in V
        """
        return float(self.ask("SOUR%d:VOLT:LEVel:IMM:LOW?" % channel))

    def set_low_amplitude(self, amplitude: float, channel: int = 1) -> None:
        """
        This command sets the low level of the output amplitude
        for the specified channel

        :param amplitude: the amplitude in V
        :param channel: the output channel int from 1 to 2
        :return: None
        """
        self.write("SOUR%d:VOLT:LEVel:IMM:LOW %gV" % (channel, amplitude))

    def high_amplitude(self, channel: int = 1) -> float:
        """
        This command queries the high level of the output amplitude
        for the specified channel

        :param channel: the output channel int from 1 to 2
        :return: The amplitude in V
        """
        return float(self.ask("SOUR%d:VOLT:LEVel:IMM:HIGH?" % channel))

    def set_high_amplitude(self, amplitude, channel: int = 1) -> None:
        """
        This command sets the high level of the output amplitude
        for the specified channel

        :param amplitude: the amplitude in V
        :param channel: the output channel int from 1 to 2
        """
        self.write("SOUR%d:VOLT:LEVel:IMM:HIGH %gV" % (channel, amplitude))

    ############################################################################
    #                           Marker configuration                           #
    ############################################################################

    def marker_polarity(self, channel: int = 1, marker_channel: int = 1):
        """
        This command queries the trigger output polarity; the polarity
        can be positive or negative.

        :param channel: the channel 1 or 2
        :param marker_channel:
        :return: the polarity: 'positive' or 'negative'
        """
        raise NotImplemented

    def set_marker_polarity(self, polarity: Literal['positive', 'negative'] = 'positive',
                            channel: int = 1, marker_channel: int = 1) -> None:
        """
        This command sets the trigger output polarity; the polarity
        can be positive or negative.

        :param channel: the channel 1 or 2
        :param marker_channel:
        :param polarity: the polarity: 'positive' or 'negative'
        :return: None
        """
        raise NotImplemented

    def marker_amplitude(self, channel: int = 1, marker_channel: int = 1) -> float:
        """
        This command queries the marker output voltage level

        :param channel: the channel 1 or 2
        :param marker_channel: the marker number 1 or 2
        :return: the amplitude in V
        """
        return float(self.ask("SOURCE%d:MARKER%d:VOLTAGE:AMPLITUDE?" % (channel, marker_channel)))

    def set_marker_amplitude(self, amplitude: float, channel: int = 1, marker_channel: int = 1) -> None:
        """
        This command sets the marker voltage level. The marker_high, marker_low,
        marker_offset may be changed by this configuration

        :param channel: the channel 1 or 2
        :param amplitude: the amplitude in V
        :param marker_channel: the marker number 1 or 2
        :return: None
        """
        self.write("SOURCE%d:MARKER%d:VOLTAGE:AMPLITUDE %g" % (channel, marker_channel, amplitude))

    def marker_high(self, channel: int = 1, marker_channel: int = 1) -> float:
        """
        This command queries the marker high voltage level

        :param channel: the channel 1 or 2
        :param marker_channel: the marker number 1 or 2
        :return: high voltage level in V
        """
        return float(self.ask("SOURCE%d:MARKER%d:VOLTAGE:HIGH?" % (channel, marker_channel)))

    def set_marker_high(self, voltage: float, channel: int = 1, marker_channel: int = 1) -> None:
        """
        This command sets the marker high voltage level. The marker_amplitude,
        marker_low, marker_offset may be changed by this configuration

        :param channel: the channel 1 or 2
        :param voltage: high voltage level in V
        :param marker_channel: the marker number 1 or 2
        :return: None
        """
        self.write("SOURCE%d:MARKER%d:VOLTAGE:HIGH %g" % (channel, marker_channel, voltage))

    def marker_low(self, channel: int = 1, marker_channel: int = 1) -> float:
        """
        This command queries the marker low voltage level

        :param channel: the channel 1 or 2
        :param marker_channel: the marker number 1 or 2
        :return: low voltage level in V
        """
        return float(self.ask("SOURCE%d:MARKER%d:VOLTAGE:LOW?" % (channel, marker_channel)))

    def set_marker_low(self, voltage: float, channel: int = 1, marker_channel: int = 1) -> None:
        """
        This command sets the marker low voltage level. The marker_high,
        marker_amplitude, marker_offset may be changed by this  configuration

        :param channel: the channel 1 or 2
        :param voltage: low voltage level in V
        :param marker_channel: the marker number 1 or 2
        :return: None
        """
        self.write("SOURCE%d:MARKER%d:VOLTAGE:LOW %g" % (channel, marker_channel, voltage))

    def marker_offset(self, channel: int = 1, marker_channel: int = 1) -> float:
        """
        This command queries the marker low voltage level

        :param channel: the channel 1 or 2
        :param marker_channel: the marker number 1 or 2
        :return: offset voltage level in V
        """
        return float(self.ask("SOURCE%d:MARKER%d:VOLTAGE:LOW?" % (channel, marker_channel)))

    def set_marker_offset(self, offset: float, channel: int = 1, marker_channel: int = 1) -> None:
        """
        This command sets the marker offset level. The marker_high, marker_low,
        marker_offset may be changed by this configuration

        :param channel: the channel 1 or 2
        :param offset: offset voltage level in V
        :param marker_channel: the marker number 1 or 2
        :return: None
        """
        self.write("SOURCE%d:MARKER%d:VOLTAGE:OFFSET %g" % (channel, marker_channel, offset))

    ############################################################################
    #                       Trigger configuration                              #
    ############################################################################

    def play(self, wait_for_running: bool = True,
             timeout: float = 10) -> None:
        """
        Run the AWG/Func. Gen. This command is equivalent to pressing the
        play button on the front panel.

        :param wait_for_running: If True, this command is blocking while the
                instrument is getting ready to play
        :param timeout: The maximal time to wait for the instrument to play.
                Raises an exception is this time is reached.
        """
        self.write('AWGControl:RUN')
        if wait_for_running:
            start_time = time.perf_counter()
            running = False
            while not running:
                time.sleep(0.1)
                running = self.run_state() in ('running', 'waiting for trigger')
                waited_for = start_time - time.perf_counter()
                if waited_for > timeout:
                    raise RuntimeError(
                        f'Reached timeout ({timeout} s)  while waiting for instrument to play.'
                        ' Perhaps some waveform or sequence is corrupt?')

    def stop(self) -> None:
        """
        Stop the output of the instrument. This command is equivalent to
        pressing the stop button on the front panel.
        """
        self.write('AWGControl:STOP')

    def trigger_slope(
            self,
            trigger_channel: Literal['a', 'b', 'all'] = 'a') -> Literal['rising', 'falling']:
        """
        This command queries the instrument trigger input slope.
        The slope can be rising, falling

        :return the trigger slope
        """
        res = self.ask("TRIG:SLOPE? %sTRIGGER" % trigger_channel).lower().strip(" \n\"")
        # noinspection PyTypeChecker
        return 'rising' if res == 'positive' else 'falling'

    def set_trigger_slope(self, slope: Literal['rising', 'falling'],
                          trigger_channel: Literal['a', 'b', 'all'] = 'a') -> None:
        """
        This command sets  the instrument trigger input slope.
        The slope can be rising, falling

        :param trigger_channel: ``a`` or ``b`` event or ``all`` to trigger both
        :param slope: the trigger slope 'rising' or 'falling'
        """

        slope = slope.lower()
        slope = 'POSITIVE' if slope == 'rising' else 'NEGATIVE'

        trigger_channel = trigger_channel.lower()
        if trigger_channel in ('a', 'b'):
            self.write("TRIGger:SLOPe %s, %sTRIGGER" % (slope, trigger_channel))
        else:
            self.write("TRIGger:SLOPe %s, ATRIGGER; TRIGger:SLOPe %s, BTRIGGER" % (slope, slope))

    def trigger_threshold(self, trigger_channel: Literal['a', 'b'] = 'a') -> float:
        """
        This command queries the trigger input threshold voltage level.

        :param trigger_channel: ``a`` or ``b`` event or ``all`` to trigger both
        :return: threshold level from –5 V to 5 V
        """
        return float(self.ask("TRIGger:LEVel? %sTRIGGER" % trigger_channel))

    def set_trigger_threshold(self, threshold: float,
                              trigger_channel: Literal['a', 'b', 'all'] = 'a') -> None:
        """
        This command sets the trigger input threshold voltage level in Volt.

        :param trigger_channel: ``a`` or ``b`` event or ``all`` to trigger both
        :param threshold: threshold level from –5 V to 5 V
        """

        trigger_channel = trigger_channel.lower()
        if trigger_channel in ('a', 'b'):
            self.write("TRIGger:LEVel %g, %sTRIGGER" % (threshold, trigger_channel))
        else:
            self.write("TRIGger:LEVel %g, ATRIGGER; TRIGger:LEVel %g, BTRIGGER" % (threshold, threshold))

    def trigger_impedance(
            self, trigger_channel: Literal['a', 'b'] = 'a') -> Literal['50ohm', 'high']:
        """
        This command queries the trigger input impedance; it can
        be 50 Ohm or 1KOhm

        :return: the trigger input impedance: '50ohm', 'high'
        :param trigger_channel: ``a`` or ``b`` event
        """
        res = self.write("TRIGger:IMPEDANCE? %sTRIGGER" % trigger_channel)
        # noinspection PyTypeChecker
        return '50ohm' if res == '50' else 'high'

    def set_trigger_impedance(self, impedance: Literal['50ohm', 'high'] = '50ohm',
                              trigger_channel: Literal['a', 'b', 'all'] = 'a') -> None:
        """
        This command sets the trigger input impedance; it can
        be 50 Ohm or high (that correspond to 1 kOhm)

        :param trigger_channel: ``a`` or ``b`` event or ``all`` to trigger both
        :param impedance: trigger input impedance '50ohm', 'high'
        :return: None
        """

        impedance = '1000' if impedance.lower() == 'high' else '50'
        trigger_channel = trigger_channel.lower()

        if trigger_channel in ('a', 'b'):
            self.write("TRIGger:IMPEDANCE %s, %sTRIGGER" % (impedance, trigger_channel))
        else:
            self.write("TRIGger:IMPEDANCE %s, ATRIGGER; TRIGger:IMPEDANCE %s, BTRIGGER"
                       % (impedance, impedance))

    def trigger(self, trigger_channel: Union[Literal['a', 'b', 'all']] = 'a') -> None:
        """
        This command generates a trigger A or B event.
        :param trigger_channel: ``a`` or ``b`` event or ``all`` to trigger both
        """
        trigger_channel = trigger_channel.lower()
        if trigger_channel in ('a', 'b'):
            self.write("TRIGGER:IMMEDIATE %sTRIGGER" % trigger_channel)
        else:
            self.write("TRIGGER:IMMEDIATE ATRIGGER; TRIGGER:IMMEDIATE BTRIGGER")

    def trigger_source(self, channel: int = 1):
        """
        This command returns the trigger input source of the specified channel.
        :param channel: the channel 1 or 2
        """
        source = self.ask("[SOURce[%s]:]TINPut?" % channel)
        TRIGGER_SOURCE = {'external_a': 'ATR', 'external_b': 'BTR', 'internal': 'ITR'}

        for k, v in TRIGGER_SOURCE:
            if source == v:
                return k

        raise ValueError("unexpected return from the tool")

    def set_trigger_source(self,
                           source: TriggerSourceType = 'external',
                           channel: int = 1,
                           trigger_channel: Union[Literal['a', 'b']] = 'a'):
        """
        This command sets the trigger input source of the specified channel.
        :param source: the trigger source 'external' or 'timer'
        :param channel: the channel 1 or 2
        :param trigger_channel: the trigger input channel 'a' or 'b'
        """
        TRIGGER_SOURCE = {'external': 'EXT', 'timer': 'ITR'}
        trig_chan = {'a': 'ATRIGGER', 'b': 'BTRIGGER'}
        if source == 'external':
            self.write("SOURce%d:TINPut %s" % (channel, trig_chan[trigger_channel]))
        else:
            self.write("SOURce%d:TINPut %s" % (channel, TRIGGER_SOURCE[source]))

    ############################################################################
    #                               System                                     #
    ############################################################################
    def error(self):
        """ Returns a tuple of an error code and message from the fist
        error in the stack """
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
        time.sleep(0.5)
        self.sequence_list_clear()
        self.waveform_list_clear()

    def shutdown(self) -> None:
        """ Ensures that the current or voltage is turned to zero
        and disables the output. """
        self.stop()
        self.set_output(False, 1)
        self.set_output(False, 2)
        self.isShutdown = True
        log.info("Shutting down %s.", self.name)
