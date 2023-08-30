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
from __future__ import annotations

import logging
import time
from typing import Optional, Union, Literal, Final, List

from ...instruments import Instrument

# Setup logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

FunctionType: Final = Literal['current dc', 'current', 'voltage dc', 'voltage', 'resistance']
TraceDataOption: Final = Literal["data", "relative", "reading", "seconds", "time", "timestamp"]
TriggerEdgeType: Final = Literal['falling', 'rising', 'either']


class Keithley2450(Instrument):
    """
    Represents the Keithely 2450 SourceMeter and provides a high-level interface
    for interacting with the instrument.


    Attributes:
    ===========


        **TRACE_DATA_OPTION**: The different data that will be store
         in the tool buffer.

        ===========  ===========  ==============================================
        key          value        comment
        ===========  ===========  ==============================================
        data         DATE         The buffer style must be set to the style
                                  standard or full to use this option

        relative     REL          The relative time when the data point
                                  was measured

        reading      READ         The measurement reading

        seconds      SEC          The seconds in UTC format when the data point
                                  was measured

        time         TIME         The time when the data point was measured

        timestamp    TST          The timestamp when the data point was measured
        ===========  ===========  ==============================================


        **FUNCTION**: The different kind of function the tool can be
        (also called mode in some documentation)


        ===========  ===========  ==============================================
        key          value        comment
        ===========  ===========  ==============================================
        current dc   CURR         ..
        current      CURR         for legacy and compatibility
        voltage dc   VOLT         ..
        voltage      VOLT         for legacy and compatibility
        resistance   RES'         ..
        ===========  ===========  ==============================================
    """

    FUNCTION: Final = {
        'current dc': 'CURR',
        'current': 'CURR',  # for legacy and compatibility
        'voltage dc': 'VOLT',
        'voltage': 'VOLT',  # for legacy and compatibility
        'resistance': 'RES',
    }

    TRACE_DATA_OPTION: Final = {
        "data": "DATE",
        "relative": "REL",
        "reading": "READ",
        "seconds": "SEC",
        "time": "TIME",
        "timestamp": "TST"
    }

    TRIGGER_EDGE: Final = {
        'falling': 'FALL',  # Detects falling-edge triggers as input
        'rising': 'RIS',  # Detects rising-edge triggers as input
        'either': 'EITH'  # Detects rising- or falling-edge triggers as input'
    }

    def ask(self, command: str) -> str:
        """ Writes the command to the instrument through the adapter
        and returns the read response.

        :param command: command string to be sent to the instrument
        """
        return self.adapter.ask(command).strip("\"\n\r ")

    ############################################################################
    #                               Trigger                                    #
    ############################################################################

    def trigger_ext_edge(self) -> TriggerEdgeType:
        """
        This command get the type of edge that is detected as an input on the
        external trigger in line

        =================  ===================================================
        return value       Description
        =================  ===================================================
        falling            detects falling-edge triggers as input
        rising             detects rising-edge triggers as input
        either             detects rising- or falling-edge triggers as input
        =================  ===================================================

        :return a key from :code:TRIGGER_EDGE
        """

        res: str = self.ask(":TRIG:EXT:IN:EDGE?")

        for k, v in self.TRIGGER_EDGE.items():
            if res.upper().strip() == k:
                return v  # type: ignore

    def set_trigger_ext_edge(self, detected_edge: TriggerEdgeType):
        """
        This command sets the type of edge that is detected as an input on
        the external trigger in line

        =================  ===================================================
        return value       Description
        =================  ===================================================
        falling            detects falling-edge triggers as input
        rising             detects rising-edge triggers as input
        either             detects rising- or falling-edge triggers as input
        =================  ===================================================

        :param detected_edge: a key from :code:TRIGGER_EDGE
        """

        self.write(":TRIG:EXT:IN:EDGE %s" % self.TRIGGER_EDGE[detected_edge])

    def trigger_model_start(self):
        """
        When you run the trigger model, the existing instrument settings are
        used for any actions. Trigger-model operation is an overlapped process.

        This means that you can run other commands while a trigger model is
        running if they do not conflict with trigger model operation.
        For example, you can print the buffer contents, but you cannot change
        the measure function.
        """
        self.write("INIT")
        time.sleep(0.1)

    def trigger_model_pause(self):
        """
        You can pause the trigger model while it is in progress by using the
        pause command. To restart the trigger model after pausing, use
        the resume command
        """
        self.write(":TRIG:PAUS")

    def trigger_model_resume(self):
        """
        Restart the trigger model after pausing, use the resume command
        """
        self.write(":TRIG:RES")
        time.sleep(0.1)

    def trigger_model_abort(self):
        """
        You can stop the trigger model while it is in progress. When you stop
        the trigger model, all trigger model commands on the instrument
        are terminated
        """
        self.write(":ABOR")

    def trigger_model_state(self) -> str:
        """
        The trigger model can be in one of several states. The following table
        describes the trigger model states This table also describes the
        indicator you get from the remote interface.

        ===============  =======================================================
        SCPI remote      Description
        ===============  =======================================================
        ``aborted``      The trigger model was stopped before it completed
        ``idle``         Trigger model is stopped
        ``empty``        No blocks are defined
        ``inactive``     Encountered system settings that do not yield a reading
        ``running``      Trigger model is running
        ``waiting``      The trigger model in a wait block for more than 100ms
        ===============  =======================================================

        """
        return str(self.ask(":TRIG:STAT?")).lower()

    def trigger_model_load_empty(self):
        """
        Load an empty model from the trigger-model templates

        The DMM7510 includes trigger-model templates for common applications.
        You can use these templates without changing them, or you can modify
        them to meet the needs of your application.

        """
        self.write(':TRIG:LOAD "empty"')

    def trigger_bloc_branch_event(self, block_number: int, branch_to_block: int,
                                  event: str = "external"):
        """
        This command branches to a specified block when a specified trigger
        event occurs

        The branch-on-event block goes to a branching block after a specified
        trigger event occurs. If the trigger event has not yet occurred when the
        trigger model reaches the branch-on-event block, the trigger model
        continues to execute the blocks in the normal sequence. After the
        trigger event occurs, the next time the trigger model reaches the
        branch-on-event block, it goes to the branching block. If you set the
        branch event to none, an error is generated when you run the trigger
        model.

        If you are using a timer, it must be started before it can expire.
        One method to start the timer in the trigger model is to include a
        Notify block before the On Event block. Set the Notify block to use
        the same timer as the On Event block.

        The following table shows the constants for the events

        ===============  =======================================================
        event            Description
        ===============  =======================================================
        ``atrigger``     Analog trigger
        ``blender<n>``   Trigger event blender <n> (up to two), which combines
        ``command``      A command interface trigger (like a GPIB *TRG)
        ``digio<n>``     Line edge detected on digital input line <n> (1 to 6)
        ``display``      Front-panel TRIGGER key press DISPlay
        ``lan<n>``       Appropriate LXI trigger packet is received on
                         LAN trigger object<n> (1 to 8)
        ``none``         No trigger event
        ``NOTify<n>``    The trigger model generates a trigger event when it
                         executes the notify block
        ``TIMer<n>``     Trigger timer <n> (1 to 4) expired
        ``TSPLink<n>``   Line edge detected on TSP-Link synchronization line <n>
        ===============  =======================================================

        :param branch_to_block: The block number to execute when the trigger
        model reaches this block

        :param event: The event that must occur before the trigger model
        branches the specified block

        :param block_number: The sequence of the block in the trigger model
        """
        self.write(":TRIG:BLOC:BRAN:EVEN %d, \"%s\",  %d" % (block_number, event, branch_to_block))

    def trigger_bloc_buffer_clear(self, block_number: int,
                                  buffer_name: str = "defbuffer1"):
        """
        This command defines a trigger model block that clears the reading buffer.

        If you remove a trigger model block, you can use this block as a
        placeholder for the block number so that you do not need to renumber
        the other blocks.

        :param block_number: The sequence of the block in the trigger model
        :param buffer_name: The name of the buffer, if no buffer is defined, defbuffer1 is used
        """
        self.write("TRIG:BLOC:BUFF:CLE %d, \"%s\"" % (block_number, buffer_name))

    def trigger_bloc_nop(self, block_number: int):
        """
        This command creates a placeholder that performs no action in
        the trigger model;

        :param block_number: The sequence of the block in the trigger model
        """
        self.write(":TRIG:BLOC:NOP %d" % block_number)

    def trigger_bloc_delay_const(self, block_number: int, delay: float):
        """
        This command adds a constant delay to the execution of a trigger model.

        :param block_number: The sequence of the block in the trigger model
        :param delay: The amount of time in seconds to delay (167 ns to 10 ks; 0 for no delay)
        """
        self.write("TRIG:BLOC:DEL:CONS %d, %.9g" % (block_number, delay))

    def trigger_bloc_notify(self, block_number: int, notify_id: int):
        """
        Define a trigger model block that generates a trigger event and
        immediately continues to the next block.

        When trigger model execution reaches a notify block, the instrument
        generates a trigger event and immediately continues to the next block.

        Other commands can reference the event that the notify block generates.
        This assigns a stimulus somewhere else in the system. For example,
        you can use the notify event as the stimulus of a hardware trigger line,
        such as a digital I/O line.

        When you call this event, you use the format NOTIFY followed by the
        notify identification number. For example, if you assign notify_id as 4,
        you would refer to it as NOTIFY4 in the command that references it.

        :param block_number: The sequence of the block in the trigger model

        :param notify_id: The identification number of the notification; 1 to 8
        """
        self.write(":TRIG:BLOC:NOT %d, %d" % (block_number, notify_id))

    def trigger_bloc_branch_always(self, block_number: int, branch_to_block: int):
        """
        This command defines a trigger model block that always goes
        to a specific block.

        :param block_number: The sequence of the block in the trigger model

        :param branch_to_block: The block number to execute when the trigger
        model reaches this block
        """

        self.write(":TRIG:BLOC:BRAN:ALW %d, %d" % (block_number, branch_to_block))

    def trigger_bloc_measurement(self, block_number: int, buffer_name: str = "defbuffer1", count: Union[int, str] = 1):
        """
        This block triggers measurements based on the measure function that is
        selected when the trigger model is initiated. When trigger model
        execution reaches this block:
            1. The instrument begins triggering measurements.
            2. The trigger model execution waits for the measurement to be made.
            3. The instrument processes the reading and places it into
               the specified reading buffer.

        If you are defining a user-defined reading buffer, you must create it
        before you define this block. When you set the count to a finite value,
        trigger model execution does not proceed until all operations are complete.

        The count parameter can be :
            - A specific integer value (default is ``1`` if nothing set)
            - Infinite (run continuously until stopped): ``INF``
            - Stop infinite to stop the count: ``0``
            - Use most recent count value (default): ``AUTO``

        If you set the count to infinite, the trigger model executes subsequent
        blocks when the measurement is made; the triggering of measurements
        continues in the background until the trigger model execution reaches
        another measure/digitize block or until the trigger model ends.
        To use infinite, there must be a block after the measure/digitize block
        in the trigger model, such as a wait block. If there is no subsequent
        block, the trigger model stops, which stops measurements.

        When you set the count to auto, the trigger model uses the count value
        that is active for the selected function instead of a specific value.
        You can use this with configuration lists to change the count value
        each time a measure/digitize block is encountered.

        :param block_number: The sequence of the block in the trigger model

        :param buffer_name: The name of the buffer, if no buffer is defined,
        ``defbuffer1`` is used

        :param count: Specifies the number of readings to make before moving
        to the next block in the trigger model
        """

        # the TRIG:BLOCK:MEAS is used instead TRIG:BLOCK:MDIG
        # to be compatible with older firmware version
        self.write(':TRIG:BLOC:MEAS %d, "%s", %s' % (block_number, buffer_name, count))

    def trigger_external_out_stimulus(self) -> str:
        """
        This command selects the event that causes a trigger to be asserted
        on the external output line.

        ==================  ====================================================
        SCPI remote         Description
        ==================  ====================================================
        ``atrigger``        The trigger model was stopped before it completed
        ``external``        External trigger in
        ``none``            No trigger event
        ``notify<n>``       Notify trigger block <n> of the trigger model when
                            it executes the notify block
        ==================  ====================================================

        :return: The event to use as a stimulus
        """
        return str(self.ask(":TRIG:EXT:OUT:STIM?")).lower()

    def set_trigger_external_out_stimulus(self, event: str):
        """
        This command return the event that causes a trigger to be asserted on
        the external output line.

        ==================  ====================================================
        SCPI remote         Description
        ==================  ====================================================
        ``atrigger``        The trigger model was stopped before it completed
        ``external``        External trigger in
        ``none``            No trigger event
        ``notify<n>``       Notify trigger block <n> of the trigger model when
                            it executes the notify block
        ==================  ====================================================

        :param event: The event to use as a stimulus
        """
        self.write(":TRIG:EXT:OUT:STIM %s" % event)

    def set_trigger_external_out_logic(self, logic_type: Literal["positive", "positive"]):
        """
        This command sets the output logic of the trigger event generator
        to positive or negative for the external I/O out line.

        ==================  ===========================
        logic Type          Description
        ==================  ===========================
        ``positive``        Assert a TTL-high pulse
        ``negative``        Assert a TTL-low pulse
        ==================  ===========================

        :param logic_type: The output logic of the trigger generator
        """
        self.write(":TRIG:EXT:OUT:LOG %s" % logic_type)

    def trigger_external_out_logic(self):
        """
        This command get the output logic of the trigger event generator
        to positive or negative for the external I/O out line.

        ==================  ===========================
        logic Type          Description
        ==================  ===========================
        ``positive``        Assert a TTL-high pulse
        ``negative``        Assert a TTL-low pulse
        ==================  ===========================

        :return: The output logic of the trigger generator
        """
        return self.ask(":TRIG:EXT:OUT:LOG?")

    def trigger_digital_out_logic(self, line_nb: int) -> str:
        """
        This command queries the output logic of the trigger event generator
        to positive or negative for the specified line. The line must be in
        trigger mode.

        ==================  ===========================
        logic Type          Description
        ==================  ===========================
        ``positive``        Assert a TTL-high pulse
        ``negative``        Assert a TTL-low pulse
        ==================  ===========================

        :param line_nb the digital i/o line between 1 and 6
        :return: The output logic of the trigger generator
        """
        return str(self.ask(":TRIG:DIG%d:OUT:LOG?" % line_nb)).lower()

    def set_trigger_digital_out_logic(self, line_nb: int,
                                      logic_type: Literal["positive", "positive"]):
        """
        This command sets the output logic of the trigger event generator to
        positive or negative for the specified line.
        The line must be in trigger mode.

        ==================  ===========================
        logic Type          Description
        ==================  ===========================
        ``positive``        Assert a TTL-high pulse
        ``negative``        Assert a TTL-low pulse
        ==================  ===========================

        :param logic_type: The output logic of the trigger generator
        :param line_nb the digital i/o line between 1 and 6
        :return: The output logic of the trigger generator
        """
        self.write(":TRIG:DIG%d:OUT:LOG %s" % (line_nb, logic_type))

    def trigger_digital_out_stimulus(self, line_nb: int) -> str:
        """
        This command selects the event that causes a trigger to be asserted
         on the external output line.

        ==================  ====================================================
        SCPI remote         Description
        ==================  ====================================================
        ``atrigger``        The trigger model was stopped before it completed
        ``external``        External trigger in
        ``none``            No trigger event
        ``notify<n>``       Notify trigger block <n> of the trigger model when
                            it executes the notify block
        ==================  ====================================================

        :param line_nb: line_nb the digital i/o line between 1 and 6
        :return: The event to use as a stimulus
        """
        return str(self.ask(":TRIG:DIG%d:OUT:STIM?" % line_nb)).lower()

    def set_trigger_digital_out_stimulus(self, line_nb: int, event: str):
        """
        This command selects the event that causes a trigger to be asserted
        on the digital output line

        ==================  ====================================================
        SCPI remote         Description
        ==================  ====================================================
        ``atrigger``        The trigger model was stopped before it completed
        ``external``        External trigger in
        ``none``            No trigger event
        ``notify<n>``       Notify trigger block <n> of the trigger model when
                            it executes the notify block
        ==================  ====================================================

        :param line_nb: line_nb the digital i/o line between 1 and 6
        :param event: The event to use as a stimulus
        """
        self.write(":TRIG:DIG%d:OUT:STIM %s" % (line_nb, event))

    ###################
    #    digit i/o    #
    ###################

    def set_digital_io_mode(self, line_nb: int,
                            line_type: Literal["digital", "trigger"],
                            line_direction: Literal["in", "out"]):
        """
        This command sets the mode of the digital I/O line to be a digital line,
        trigger line, or synchronous line and sets the line to be input,
        output, or open-drain.

        ==================  ==================================================
        line_type           Description
        ==================  ==================================================
        ``digital``         Allow direct digital control of the line
        ``trigger``         Configure for trigger control
        ``synchronous``     Configure as a synchronous master or acceptor
        ==================  ==================================================

        :param line_direction:
        :param line_type:
        :param line_nb: line_nb the digital i/o line between 1 and 6
        """
        self.write(":DIG:LINE%d:MODE %s, %s" % (line_nb, line_type, line_direction))

    ############################################################################
    #                             trace                                        #
    ############################################################################

    def trace_data(self, start_index: int, stop_index: int,
                   buffer_elements: TraceDataOption = "reading",
                   buffer_name: str = "defbuffer1") -> Union[List[float], List[str]]:
        """
        This command returns specified data elements from a specified reading buffer

        The options for 'buffer_name' are described in the following table

        ====================  ==================================================
        buffer_elements       Description
        ====================  ==================================================
        ``reading``           The measurement reading
        ``relative``          The relative time when the data point was measured
        ``date``              The buffer style must be set to the style standard
                              or full to use this option
        ``seconds``           The seconds in UTC format
        ``time``              The time when the data point was measured
        ``timestamp``         The timestamp when the data point was measured
        ====================  ==================================================

        .. Warning
            because of  GPIB limitation, it is unadvised to retrieve more than
            200 values at each request

        :param start_index: Beginning index of the buffer to return;
        must be 1 or greater

        :param stop_index: Ending index of the buffer to return

        :param buffer_name: A string that indicates the reading buffer,
        if no buffer is specified, ``defbuffer1`` is used

        :param buffer_elements: A list of elements in the buffer to print;
        if nothing is specified, ``reading`` is used

        :return a list of float if buffer_elements is reading, a list of str otherwise
        """
        res = self.ask("TRACe:DATA? %d, %d, \"%s\", %s" %
                       (start_index, stop_index, buffer_name,
                        self.TRACE_DATA_OPTION[buffer_elements]))

        if buffer_elements == "reading":
            return list(map(float, res.split(",")))
        else:
            return res.split(",")

    def trace_clear(self, buffer_name: str = "defbuffer1"):
        """
        This command clears all readings and statistics from the specified buffer.

        :param buffer_name: the reading buffer the default buffers
        (``defbuffer1`` or ``defbuffer2``) or a user-defined buffer
        """
        self.write(":TRACe:CLEar \"%s\"" % buffer_name)

    def trace_end(self, buffer_name: str = "defbuffer1"):
        """
        This command indicates the last index in a reading buffer.

        :param buffer_name: A string that indicates the reading buffer,
        if no buffer is specified, ``defbuffer1`` is used

        :return: last index in a reading buffer
        """

        return int(self.ask(":TRACE:ACT:END? \"%s\"" % buffer_name))

    def trace_start(self, buffer_name: str = "defbuffer1"):
        """
        This command indicates the starting index in a reading buffer.

        :param buffer_name: A string that indicates the reading buffer,
        if no buffer is specified, ``defbuffer1`` is used

        :return: first index in a reading buffer
        """

        return int(self.ask(":TRACE:ACT:START? \"%s\"" % buffer_name))

    def trace_size(self, buffer_name: str = "defbuffer1"):
        """
        This command contains the number of readings in the
        specified reading buffer.

        :param buffer_name: A string that indicates the reading buffer,
        if no buffer is specified, ``defbuffer1`` is used

        :return:  number of readings in the buffer
        """
        return int(self.ask(":TRACe:ACTual? \"%s\"" % buffer_name))

    def trace_max_size(self, buffer_name: str = "defbuffer1"):
        """
        This command contains the number of readings in the
        specified reading buffer.

        :param buffer_name: A string that indicates the reading buffer,
        if no buffer is specified, ``defbuffer1`` is used

        :return:  maximum number of readings in the buffer
        """
        return int(self.ask(":TRACe:POINts? \"%s\"" % buffer_name))

    def set_trace_max_size(self, new_size, buffer_name: str = "defbuffer1"):
        """
        This command allows you to change or view how many readings a buffer can
        store. Changing the size of a buffer will cause any existing data in the
        buffer to be lost.

        If you select 0, the instrument creates the largest reading buffer
        possible based on the available memory when the buffer is created.

        The overall capacity of all buffers stored in the instrument can be
        up to 7 500 000 readings for standard reading buffers and 11000020 for
        compact reading buffers

        :param buffer_name: A string that indicates the reading buffer,
        if no buffer is specified, ``defbuffer1`` is used

        :param new_size: the wanted buffer maximum size
        """
        self.write(":TRACe:POINts %d, \"%s\"" % (new_size, buffer_name))

    def set_trace_fill_mode(self, fill_type: str, buffer_name: str = "defbuffer1"):
        """
        This command determines if a reading buffer is filled continuously or
        is filled once and stops

        When a reading buffer is set to fill once, no data is overwritten
        in the buffer. When the buffer is filled, no more data is stored in that
        buffer and new readings are discarded.

        When a reading buffer is set to fill continuously, the oldest data is
        overwritten by the newest data after the buffer fills.

        When you change the fill mode of a buffer, any data in the buffer
        is cleared

        ===================  ===========================================
        fill_type            Description
        ===================  ===========================================
        ``continuous``       Fill the buffer continuously
        ``once``             Fill the buffer, then stop
        ===================  ===========================================

        :param buffer_name: A string that indicates the reading buffer,
        if no buffer is specified, ``defbuffer1`` is used

        :param fill_type: ``continuous`` or ``once``
        """
        self.write(":TRACe:FILL:MODE %s, \"%s\"" % (fill_type, buffer_name))

    def trace_fill_mode(self, buffer_name: str = "defbuffer1"):
        """
        This command determines if a reading buffer is filled continuously or
        is filled once and stops

        When a reading buffer is set to fill once, no data is overwritten in
        the buffer. When the buffer is filled, no more data is stored in that
        buffer and new readings are discarded.

        When a reading buffer is set to fill continuously, the oldest data
        is overwritten by the newest data after the buffer fills.

        When you change the fill mode of a buffer, any data in the buffer
        is cleared

        ===================  ===========================================
        fill_type            Description
        ===================  ===========================================
        ``continuous``       Fill the buffer continuously
        ``once``             Fill the buffer, then stop
        ===================  ===========================================

        :param buffer_name: A string that indicates the reading buffer,
        if no buffer is specified, ``defbuffer1`` is used

        :return ``continuous`` or ``once``
        """
        return self.write(":TRACe:FILL:MODE %s \"%s\"" % buffer_name).lower()

    def _function_source_gpib_code(self, function: Optional[FunctionType]) -> str:
        if function is None:
            return self.ask("SOUR:FUNC?").upper()
        else:
            return self.FUNCTION[function]

    def _function_sense_gpib_code(self, function: Optional[FunctionType]) -> str:
        if function is None:
            res = self.ask("SENS:FUNC?").upper()

            if "CURR:DC" in res:
                return "CURR"
            elif "VOLT:DC" in res:
                return "VOLT"
            else:
                return res
        else:
            return self.FUNCTION[function]

    def sense_function(self) -> str:
        """
        return the configured sensor measurements function, which can
        take the values: ``current dc``, ``voltage dc`` and ``resistance``

        :return : the tool configured function
        """
        res = self.ask("SENS:FUNC?").upper()

        for k, v in self.FUNCTION.items():
            if res == v:
                if k != "current" and k != "voltage":
                    return v

    def set_sense_function(self, new_function: FunctionType):
        """
        Set the configured measurements function, which can take the values:

        ===================  ===================================================
        function             comment
        ===================  ===================================================
        current dc           ..
        current              alias of ``current dc`` for compatibility
        voltage dc           ..
        voltage              alias of ``voltage dc`` for compatibility
        resistance           ..
        ===================  ===================================================

        :param new_function: a string chosen in the function table
        """
        self.write("SENS:FUNC \"%s\"" % self.FUNCTION[new_function.lower()])
        time.sleep(0.1)  # need a bit of time for the k2450 internal switch to activate...

    def source_function(self) -> FunctionType:
        """
        return the configured source function, which can
        take the values: ``current dc``, ``voltage dc`` and ``resistance``

        :return : the tool configured function
        """
        res = self.ask(":SOUR:FUNC?").upper().strip()

        for k, v in self.FUNCTION.items():
            if res in v:
                if k != "current" and k != "voltage":
                    return k  # type: ignore

    def set_source_function(self, new_function: FunctionType):
        """
        Set the configured measurements function, which can take the values:

        ===================  ===================================================
        function             comment
        ===================  ===================================================
        current dc           ..
        current              alias of ``current dc`` for compatibility
        voltage dc           ..
        voltage              alias of ``voltage dc`` for compatibility
        resistance           ..
        ===================  ===================================================

        :param new_function: a string chosen in the function table
        """
        self.write("SOUR:FUNC %s" % self.FUNCTION[new_function])
        # need a bit of time for the k7510 internal switch to activate...
        time.sleep(0.75)

    ############################################################################
    #                              Measurement                                 #
    ############################################################################

    def source_range(self, function: Optional[FunctionType] = None) -> float:
        """
        This command return the range for the source for the
        selected source function.

        The range is return in float in the principal unit with no subunit
        (e.g. A, V, Ω or F). If ``function`` is ``None``, the function will use
        the function in which the tool already is.

        The available ranges are:

         ======================  ===================================================
         function                ranges
         ======================  ===================================================
         current dc              10nA, 100nA, 1µA, 10µA, 100µA, 1mA, 10mA, 100mA, 1A
         voltage dc              20mV, 200mV, 2V, 20V, 200V
         ======================  ===================================================

        :param function: The function to which the setting is return
        """

        return float(self.ask(":SOUR:%s:RANG?" % self._function_source_gpib_code(function)))

    def set_source_range(self, new_range: float, function: Optional[FunctionType] = None):
        """
        This command selects the range for the source for the selected source function.

        If ``function`` is ``None``, the function will use the function in which
        the tool already is. The available ranges are:

         ======================  ===================================================
         function                ranges
         ======================  ===================================================
         current dc              10nA, 100nA, 1µA, 10µA, 100µA, 1mA, 10mA, 100mA, 1A
         voltage dc              20mV, 200mV, 2V, 20V, 200V
         ======================  ===================================================

        :param new_range: the new range set
        :param function: The function to which the setting is set
        """

        self.write(":SOUR:%s:RANG %s" % (self._function_source_gpib_code(function), new_range))

    def set_source_auto_range(self, auto_range: bool = True, function=None):
        """
        Sets the source to use or note auto-range.

        If ``function`` is ``None``, the function will use the function in which
        the tool already is. The function can be : current dc (or current),
        voltage dc (or voltage).

        :param auto_range: if True activate the auto range
        :param function: A valid function name, or None for the active function
        """
        auto = "1" if auto_range else '0'

        self.write(":SOUR:%s:RANG:AUTO %s" % (self._function_source_gpib_code(function), auto))

    def set_source_high_capacitance(self, high_capacitance: bool = True, function=None):
        """
        The 2450 high-capacitance mode can prevent problems when you are
        measuring low current and driving a capacitive load. In this situation,
        you may see overshoot, ringing, and instability. This occurs because the
        pole formed by the load capacitance and the current range resistor can
        cause a phase shift in the voltage-control loop of the instrument.

        The actual operating conditions for a given capacitive load can vary.
        This is due to the large dynamic range of the current measurement
        capability and wide range of internal resistors in the instrument.
        Some test applications require capacitors larger than 20 nF.
        In these applications, you can use the high-capacitance mode to minimize
        overshoot, ringing, and instability

        :param high_capacitance: if True activate the high capacitance mode
        :param function: A valid function name, or None for the active function
        """

        cap = "ON" if high_capacitance else 'OFF'
        self.write("SOUR:%s:HIGH:CAP  %s" % (self._function_source_gpib_code(function), cap))

    def sense_range(self, function: Optional[FunctionType] = None) -> float:
        """
        Return sensor the range for the function.

        The range is return in float in the principal unit with no subunit
        (e.g. A, V, Ω or F). If ``function`` is ``None``, the function will
         use the function in which the tool already is.

        The available ranges are:

         ===========================  ==================
         function                     amplitude
         ===========================  ==================
         current dc (or current)      −1.05A to 1.05A
         voltage dc  (or voltage)     −210V to 210V
         resistance                   20Ω to 200MΩ
         ===========================  ==================

        :param function: The function to which the setting is return
        """

        funtion = self._function_sense_gpib_code(function)
        return float(self.ask(":SENS:%s:RANG:AUTO 0;:SENS:%s:RANG?" % (funtion, funtion)))

    def set_sense_range(self, new_range: float, function: Optional[FunctionType] = None):
        """ set the sensor the range for the function

            If ``function`` is ``None``, the function will use the function in
            which the tool already is. The available ranges are:

             ===========================  ==================
             function                     amplitude
             ===========================  ==================
             current dc (or current)      −1.05A to 1.05A
             voltage dc  (or voltage)     −210V to 210V
             resistance                   20Ω to 200MΩ
             ===========================  ==================

            :param new_range: the new range set
            :param function: The function to which the setting is set
        """
        funtion = self._function_sense_gpib_code(function)
        self.write(":SENS:%s:RANG:AUTO 0;:SENS:%s:RANG %s" % (funtion, funtion, new_range))

    def set_sense_auto_range(self, auto_range: bool = True,
                             function: Optional[FunctionType] = None):
        """
        Sets the sensor function to use or not the auto-range.

        If ``function`` is ``None``, the function will use the function in which
        the tool already is. The available ranges are: current dc (or current),
        voltage dc (or voltage).

        :param auto_range: if True activate the auto range
        :param function: A valid function name, or None for the active function
        """
        auto = "1" if auto_range else '0'
        self.write(":SENS:%s:RANG:AUTO %s" % (self._function_sense_gpib_code(function), auto))

    def read_measurement(self, buffer_elements: str = "reading",
                         buffer_name: str = 'defbuffer1') -> Union[float, str]:
        """
        This command makes measurements, places them in a reading buffer,
        and returns the last reading. The options for 'buffer_elements' are
        described in the following table:

        ====================  ==================================================
        buffer_elements       Description
        ====================  ==================================================
        ``reading``           The measurement reading
        ``relative``          The relative time when the data point was measured
        ``date``              The buffer style must be set to the style standard
                              or full to use this option
        ``seconds``           The seconds in UTC format
        ``time``              The time when the data point was measured
        ``timestamp``         The timestamp when the data point was measured
        ====================  ==================================================

        :param buffer_name: A string that indicates the reading buffer,
        if no buffer is specified, ``defbuffer1`` is used

        :param buffer_elements: A list of elements in the buffer to print;
        if nothing is specified, ``reading`` is used

        :return a float if buffer_elements is reading, a st otherwise
        """
        res = self.ask("READ? \"%s\", %s" % (buffer_name, self.TRACE_DATA_OPTION[buffer_elements]))

        if buffer_elements == "reading":
            return float(res)
        else:
            return res

    def sense_nplc(self, function: Optional[FunctionType] = None) -> float:
        """
        This command get the time that the input signal is measured for the
        selected function. If ``function`` is ``None``, the function will use
        the function in which the tool already is.

        This command queries the amount of time that the input signal is measured.

        The amount of time is specified as the number of power line cycles
        (NPLCs). Each PLC for 60 Hz is 16.67 ms (1/60) and each PLC for 50Hz
        is 20ms (1/50). For 60 Hz, if you set the NPLC to 0.1, the measure time
        is 1.667 ms.

        This command is set for the measurement of specific functions (current,
        resistance, or voltage). The shortest amount of time results in the
        fastest reading rate, but increases the reading noise and decreases the
        number of usable digits.

        The longest amount of time provides the lowest reading noise and more
        usable digits, but has the slowest reading rate.

        Settings between the fastest and slowest number of power line cycles are
        a compromise between speed and noise.

        If you change the PLCs, you may want to adjust the displayed digits to
        reflect the change in usable digits.

        **Available function:**
            current dc (or current), voltage dc (or voltage), resistance

        :param function: The function to which the setting is get
        :return the NPLC between 0.01 and 10
        """

        return float(self.ask(":SENS:%s:NPLC?" % self._function_sense_gpib_code(function)))

    def set_sense_nplc(self, new_nplc: Union[float, str],
                       function: Optional[FunctionType] = None):
        """
        This command sets the time that the input signal is measured for the
         selected function. If ``function`` is ``None``,
         the function will use the function in which the tool already is.

        **Available function:**
            current dc (or current), voltage dc (or voltage), resistance

        **Note:**
            The NPLC is a float between 0.01 and  10
            can also be ``def``, ``min`` or ``max`` for default, minimum
            and maximum value

        :param new_nplc: The number of power-line cycles per
        measurement: 0.0005 to 12 or ``def``, ``min`` or ``max``

        :param function: The function to which the setting is set
        """

        self.write(":SENS:%s:NPLC %s" % (self._function_sense_gpib_code(function), new_nplc))
        if new_nplc < 1:
            time.sleep(0.5)

    def nplc(self, function: Optional[FunctionType] = None) -> float:
        """
        the same that ``sense_nplc``, here for compatibility
        :param function: The function to which the setting is get
        :return: the NPLC between 0.01 and 10
        """
        return self.sense_nplc(function)

    def set_nplc(self, new_nplc: Union[float, str],
                 function: Optional[FunctionType] = None):
        """
        the same that ``set_sense_nplc``, here for compatibility
        :param new_nplc: the NPLC between 0.01 and 10
        :param function: The function to which the setting is get
        """
        self.set_sense_nplc(new_nplc, function)

    def source_amplitude(self) -> float:
        """
        This command queries the output level of the voltage or current source.
        one can access only the function already setup, to change it, one can
        use ``set_function()``

        The sign of the source level dictates the polarity of the source.
        Positive values generate positive voltage or current from the high
        terminal of the source relative to the low terminal. Negative values
        generate negative voltage or current from the high terminal of the
        source relative to the low terminal. If a manual source range is
        selected, the level cannot exceed the specified range. For example,
        if the voltage source is on the 2 V range, you cannot set the voltage
        source level to 3 V. When autorange is selected, the amplitude can be
        set to any level supported by the instrument

         ===========================  ==================
         function                     amplitude
         ===========================  ==================
         current dc (or current)      −1.05A to 1.05A
         voltage dc  (or voltage)     −210V to 210V
         resistance                   20Ω to 200MΩ
         ===========================  ==================

        :return: the amplitude set on the ``function``
        """
        return float(self.ask(":SOUR:%s?" % (self._function_sense_gpib_code(None))))

    def set_source_amplitude(self, new_amplitude: float,
                             function: Optional[FunctionType] = None):
        """
        This command queries the output level of the voltage or current source.
        one can access only the function already setup, to change it, one can
        use ``set_function()``

        The sign of the source level dictates the polarity of the source.
        Positive values generate positive voltage or current from the high
        terminal of the source relative to the low terminal. Negative values
        generate negative voltage or current from the high terminal of the
        source relative to the low terminal. If a manual source range is
        selected, the level cannot exceed the specified range. For example,
        if the voltage source is on the 2 V range, you cannot set the voltage
        source level to 3 V. When autorange is selected, the amplitude can be
        set to any level supported by the instrument

         ===========================  ==================
         function                     amplitude
         ===========================  ==================
         current dc (or current)      −1.05A to 1.05A
         voltage dc  (or voltage)     −210V to 210V
         resistance                   20Ω to 200MΩ
         ===========================  ==================

        :return: the amplitude set on the ``function``
        """

        if function is None:
            fct = self.ask(":SOUR:FUNC?").upper()
        else:
            fct = self.FUNCTION[function]

        self.write(":SOUR:%s %g" % (fct, new_amplitude))

    def set_source_compliance(self, new_limit, function: Optional[FunctionType] = None) -> None:
        """
        This command sets the source limit for measurements. The values that can
        be set for this command are limited by the setting for the overvoltage
        protection limit. The 2450 cannot source levels that exceed this limit.

        If ``function`` is ``None``, the function will use the function in which
        the tool already is. Meaning, the voltage limit if the tool is in
        current source mode and the current limit if the tool is in voltage
        source mode.

        If you change the measure range to a range that is not appropriate for
        this limit, the instrument changes the source limit to a limit that is
        appropriate to the range and a warning is generated. Depending on the
        source range, your actual maximum limit value could be lower.
        The instrument makes adjustments to stay in the operating boundaries.

        This value can also be limited by the measurement range. If a specific
        measurement range is set, the limit must be 10.6% or higher of the
        measurement range. If you set the measurement range to be automatically
        selected, the measurement range does not affect the limit.

        Limits are absolute values

        =================  =====================================================
        function           The source function to which this setting applies:
        =================  =====================================================
        Current            ``current``
        Voltage            ``voltage``
        =================  =====================================================


        ==================  ====================================================
        new_limit           The limit:
        ==================  ====================================================
        Current source      1nA to 1.05A
        Voltage source      0.02V to 210V
        or for all source   ``default``, ``minimum`` and ``maximum``
        ==================  ====================================================

        """
        function = self._function_source_gpib_code(function)

        if function == "VOLT":
            self.write(":SOUR:VOLT:ILIM %g" % new_limit)
        else:
            self.write(":SOUR:CURR:VLIM %g" % new_limit)

    def source_compliance(self, function: Optional[FunctionType] = None) -> float:
        """
        This command queries the source limit for measurements. The values that
        can be set for this command are limited by the setting for the
        overvoltage protection limit. The 2450 cannot source levels that exceed
        this limit.

        If ``function`` is ``None``, the function will use the  function in
        which the tool already is. Meaning, the voltage limit if the tool is in
        current source mode and the current limit if the tool is in voltage
        source mode.

        If you change the measure range to a range that is not appropriate for
        this limit, the instrument changes the source limit to a limit that is
        appropriate to the range and a warning is generated. Depending on the
        source range, your actual maximum limit value could be lower.

        The instrument makes adjustments to stay in the operating boundaries.
        This value can also be limited by the measurement range.

        If a specific measurement range is set, the limit must be 10.6% or higher
        of the measurement range. If you set the measurement range to be
        automatically selected, the measurement range does not affect the limit.

        Limits are absolute values

        ===================  ===================================================
        function             The source function to which this setting applies
        ===================  ===================================================
        Current              ``current``
        Voltage              ``voltage``
        ===================  ===================================================

        :return: the source compliance
        """
        function = self._function_source_gpib_code(function)
        if function == "VOLT":
            return float(self.ask(":SOUR:VOLT:ILIM?"))
        else:
            return float(self.ask(":SOUR:CURR:VLIM?"))

    ############################################################################
    #                              Methods                                     #
    ############################################################################

    def __init__(self, adapter, **kwargs):
        super(Keithley2450, self).__init__(
            adapter, "Keithley 2450 SourceMeter", **kwargs
        )

    def enable_source(self):
        """
        Enables the source of current or voltage depending on the
        configuration of the instrument.
        """
        self.write("OUTPUT ON")
        time.sleep(0.1)

    def disable_source(self):
        """
        Disables the source of current or voltage depending on the
        configuration of the instrument.
        """
        self.write("OUTPUT OFF")

    def beep(self, frequency, duration):
        """
        Sounds a system beep.

        :param frequency: A frequency in Hz between 65 Hz and 2 MHz
        :param duration: A time in seconds between 0 and 7.9 seconds
        """
        self.write(":SYST:BEEP %g, %g" % (frequency, duration))

    def triad(self, base_frequency, duration):
        """
        Sounds a musical triad using the system beep.

        :param base_frequency: A frequency in Hz between 65 Hz and 1.3 MHz
        :param duration: A time in seconds between 0 and 7.9 seconds
        """
        self.beep(base_frequency, duration)
        time.sleep(duration)
        self.beep(base_frequency * 5.0 / 4.0, duration)
        time.sleep(duration)
        self.beep(base_frequency * 6.0 / 4.0, duration)

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
            log.info("Keithley 2450 reported error: %d, %s", code, message)
            code, message = self.error
            if (time.time() - t) > 10:
                log.warning("Timed out for Keithley 2450 error retrieval.")

    def errors_clear(self):
        """Clear all the errors"""
        self.write(":SYST:CLE")
        self.write(":DISP:CLE")
        self.write(":DISP:SCR HOME")

    def reset(self):
        """
        Resets the instrument and clears the tool.
        """
        self.write("*RST;:stat:pres;:*CLS;")
        time.sleep(0.1)

    def trigger(self):
        """
        Executes a bus trigger, which can be used when
        :meth:`~.trigger_on_bus` is configured.
        """
        return self.write("*TRG")

    def use_rear_terminals(self):
        """
        Enables the rear terminals for measurement, and
        disables the front terminals.
        """
        self.write(":ROUT:TERM REAR")

    def use_front_terminals(self):
        """
        Enables the front terminals for measurement, and
        disables the rear terminals.
        """
        self.write(":ROUT:TERM FRON")

    def shutdown(self):
        """
        Ensures that the current or voltage is turned to zero
        and disables the output.
        """
        log.info("Shutting down %s.", self.name)

        # self.set_source_amplitude(0)
        self.disable_source()
        self.isShutdown = True
