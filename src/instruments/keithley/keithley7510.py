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
from collections import abc
from typing import Sequence, Union, Optional, Literal, Final, Iterable

from .. import Instrument

log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

FunctionType: Final = \
    Literal['current dc', 'current', 'voltage dc', 'voltage',
            'current ac', 'voltage ac', 'resistance', 'resistance 4W', 'period',
            'frequency', 'temperature', 'diode', 'continuity', 'capacitance']

TraceDataOption: Final = \
    Literal["data", "relative", "reading",
            "seconds", "time", "timestamp"]

TriggerEdgeType: Final = Literal['falling', 'rising', 'either']


class Keithley7510(Instrument):
    """
    Represents the Keithley 7510 Multimeter and provides a high-level
    interface for interacting with the instrument. This driver is for
    the firmware version >=1.7.0

    ..code-block:: python
        dmm = Keithley7510("GPIB::1")


    **Trigger model**
    this driver contains the basic command to control the K7510 trigger model

    .. code-block:: python
            dmm.trigger_model_load_empty()
            dmm.trigger_bloc_delay_const(1, 5):
            dmm.trigger_bloc_measurement()
            dmm.trigger_model_start()

    **Attributes**:

    **TRACE_DATA_OPTION**: The different option for the what will be store in
    the tool buffer. This dictionary should not be modified

    ===========  ===========  ==================================================
    key          value        comment
    ===========  ===========  ==================================================
    data         DATE         The buffer style must be set to the style standard
                              or full to use this option
    relative     REL          The relative time when the data point was measured
    reading      READ         The measurement reading
    seconds      SEC          The seconds in UTC format
    time         TIME         The time when the data point was measured
    timestamp    TST          The timestamp when the data point was measured
    ===========  ===========  ==================================================

    **FUNCTION**: The different kind of function the tool can be (also called
    mode in some documentation) This dictionary should not be modified

    ==============  ===========  ===============================================
    key             value        comment
    ==============  ===========  ===============================================
    current dc      CURR:DC      ..
    current         CURR:DC      for legacy and compatibility
    current ac      CURR:AC      ..
    voltage dc      VOLT:DC      ..
    voltage         VOLT:DC      for legacy and compatibility
    voltage ac      VOLT:AC      ..
    resistance      RES          ..
    resistance 4W   FRES         ..
    period          PER          ..
    frequency       FREQ         ..
    temperature     TEMP         ..
    diode           DIOD         ..
    continuity      CONT         ..
    capacitance     CAP          ..
    ==============  ===========  ===============================================


    **TRIGGER_EDGE**: different kind of edge that can be detected as an input on
    the external trigger in line. This dictionary should not be modified

    ===========  ===========  ==================================================
    key          value        comment
    ===========  ===========  ==================================================
    falling      FALL         Detects falling-edge triggers as input
    rising       RIS          Detects rising-edge triggers as input
    either       EITH         Detects rising- or falling-edge triggers as input
    ===========  ===========  ==================================================

        """

    FUNCTION: Final = {
        'current dc': 'CURR:DC',
        'current': 'CURR:DC',  # for legacy and compatibility
        'current ac': 'CURR:AC',
        'voltage dc': 'VOLT:DC',
        'voltage': 'VOLT:DC',  # for legacy and compatibility
        'voltage ac': 'VOLT:AC',
        'resistance': 'RES',
        'resistance 4W': 'FRES',
        'period': 'PER',
        'frequency': 'FREQ',
        'temperature': 'TEMP',
        'diode': 'DIOD',
        'continuity': 'CONT',
        'capacitance': 'CAP'
    }

    TRIGGER_EDGE: Final = {
        'falling': 'FALL',  # Detects falling-edge triggers as input
        'rising': 'RIS',  # Detects rising-edge triggers as input
        'either': 'EITH'  # Detects rising- or falling-edge triggers as input'
    }

    TRACE_DATA_OPTION: Final = {
        "data": "DATE",  # The buffer must be standard or full to use this option
        "relative": "REL",  # The relative time when the data point was measured
        "reading": "READ",  # The measurement reading
        "seconds": "SEC",  # The seconds in UTC format when the data point was measured
        "time": "TIME",  # The time when the data point was measured
        "timestamp": "TST",  # The timestamp when the data point was measured
    }

    DIGITIZE_SOURCE_TRIGGER = {'analog trigger': 'ATRigger',
                               'manual': 'COMMand', 'external': 'EXT',
                               'timer': 'TIMer%d', 'digital io': 'DIGio%d'}

    def ask(self, command: str) -> str:
        """ Writes the command to the instrument through the adapter
        and returns the read response.

        :param command: command string to be sent to the instrument
        """
        return self.adapter.ask(command).strip("\"\n\r ")

    def _function_gpib_code(self, function: Optional[FunctionType] = None) -> FunctionType:
        """
        return the GPIB function code of function, if function is none,
        return the current configured function

        :param function: the function string name or None
        :return: GPIB function code
        """

        if function is None:

            fct = self.ask("SENS:FUNC?").upper()
            if fct == 'NONE':
                # particular case of the digitalized function
                return "DIG:" + self.ask("DIG:FUNC?").upper()  # type: ignore

            return fct  # type: ignore
        else:
            return self.FUNCTION[function]

    @staticmethod
    def __is_on_off(on_off: Union[str, int, bool]) -> str:
        """
        check if ``on_off`` is equivalent to an on or an off
        return "OFF" if on_off is ``False``, 0 or "OFF"
        (all capitalisation accepted), "ON" otherwise

        :param on_off:
        :return: "ON" or "OFF"
        """
        if str(on_off).strip().capitalize() == 'OFF' \
                or (type(on_off) is bool and on_off is False) \
                or (type(on_off) is int and on_off == 0):
            return 'OFF'
        else:
            return 'ON'

    def function(self) -> FunctionType:
        """
        return the configured measurements function, which can take the values:

        =============  =========================================================
        function       comment
        =============  =========================================================
        current dc     ..
        current ac     ..
        voltage dc     ..
        voltage ac     ..
        resistance     ..
        resistance 4   ..
        capacitance    ..
        period         ..
        frequency      ..
        temperature    ..
        diode          ..
        continuity     ..
        capacitance    ..
        =============  =========================================================

        :return : the tool configured function
        """
        res = self.ask("SENS:FUNC?").upper()

        for k, v in self.FUNCTION.items():
            if res == v:
                if k != "current" and k != "voltage":
                    return v

    def set_function(self, new_function: FunctionType):
        """
        Set the configured measurements function, which can take the values:

        =============  =========================================================
        function       comment
        =============  =========================================================
        current dc     ..
        current        alias of ``current dc`` for backward compatibility
        current ac     ..
        voltage dc     ..
        voltage        alias of ``voltage dc`` for backward compatibility
        voltage ac     ..
        resistance     ..
        resistance 4W  ..
        capacitance    ..
        period         ..
        frequency      ..
        temperature    ..
        diode          ..
        continuity     ..
        capacitance    ..
        =============  =========================================================

        :param new_function: a string chosen in the function table
        """
        self.write("SENS:FUNC \"%s\"" % self.FUNCTION[new_function])
        # need a bit of time for the k7510 internal switch to activate...
        time.sleep(0.80)

        ############################################################################

    #                             Trigger                                      #
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
        This command sets the type of edge that is detected as an input on the
        external trigger in line

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
        pause command. To restart the trigger model after pausing, use the
        resume command
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
        the trigger model, all trigger  model commands on the instrument
        are terminated
        """
        self.write(":ABOR")

    def trigger_model_state(self) -> str:
        """
        The trigger model can be in one of several states. The following table
        describes the trigger model states
        This table also describes the indicator you get from the remote interface.

        ===============  =======================================================
        SCPI remote      Description
        ===============  =======================================================
        ``aborted``      The trigger model was stopped before it completed
        ``idle``         Trigger model is stopped
        ``empty``        No blocks are defined
        ``inactive``     Instrument encountered system settings that do not
                         yield a reading
        ``running``      Trigger model is running
        ``waiting``      The trigger model has been n the wait block for
                          more than 100 ms
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

    def trigger_bloc_branch_always(
            self, block_number: int, branch_to_block: int):
        """
        This command defines a trigger model block that always goes to
        a specific block.

        :param block_number: The sequence of the block in the trigger model
        :param branch_to_block: The block number to execute when the trigger
        model reaches this block
        """

        self.write(":TRIG:BLOC:BRAN:ALW %d, %d" %
                   (block_number, branch_to_block))

    def trigger_bloc_branch_count(
            self, block_number: int, branch_to_block: int, count: int):
        """
        This command defines a trigger model block that branches to a specified
        block a specified number of times.


        :param count: The number of times to repeat
        :param block_number: The sequence of the block in the trigger model
        :param branch_to_block: The block number to execute when the trigger
        model reaches this block
        """

        self.write(":TRIG:BLOC:BRAN:COUN %d, %d, %d" %
                   (block_number, count, branch_to_block))

    def trigger_bloc_branch_event(
            self, block_number: int,
            branch_to_block: int,
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
        Notify block before the On Event block. Set the Notify block to use the
        same timer as the On Event block.

        The following table shows the constants for the events

        ===============  =======================================================
        event            Description
        ===============  =======================================================
        ``atrigger``     Analog trigger
        ``blender<n>``   Trigger event blender <n> (up to two), which combines
        ``command``      A command interface trigger (like a GPIB *TRG)
        ``digio<n>``     Line edge detected on digital input line <n> (1 to 6)
        ``display``      Front-panel TRIGGER key press DISPlay
        ``lan<n>``       Appropriate LXI trigger packet is received on LAN
                         trigger object<n> (1 to 8)
        ``none``         No trigger event
        ``NOTify<n>``    the trigger model generates a trigger event when it
                         executes the notify block
        ``TIMer<n>``     Trigger timer <n> (1 to 4) expired
        ``TSPLink<n>``   Line edge detected on TSP-Link synchronization
                         line <n> (1 to 3)
        ===============  =======================================================

        :param branch_to_block: The block number to execute when the trigger
        model reaches this block

        :param event: The event that must occur before the trigger
        model branches the specified block

        :param block_number: The sequence of the block in the trigger model
        """
        self.write(":TRIG:BLOC:BRAN:EVEN %d, \"%s\",  %d" %
                   (block_number, event, branch_to_block))

    def trigger_bloc_buffer_clear(
            self, block_number: int, buffer_name: str = "defbuffer1"):
        """
        This command defines a trigger model block that clears the reading buffer.

        If you remove a trigger model block, you can use this block as a
        placeholder for the block number so that you do not need to renumber
        the other blocks.

        :param block_number: The sequence of the block in the trigger model

        :param buffer_name: The name of the buffer, if no buffer is defined,
        defbuffer1 is used
        """
        self.write("TRIG:BLOC:BUFF:CLE %d, \"%s\"" % (block_number, buffer_name))

    def trigger_bloc_nop(self, block_number: int):
        """
        This command creates a placeholder that performs no action in the
        trigger model;

        :param block_number: The sequence of the block in the trigger model
        """
        self.write(":TRIG:BLOC:NOP %d" % block_number)

    def trigger_bloc_delay_const(self, block_number: int, delay: float):
        """
        This command adds a constant delay to the execution of a trigger model.

        :param block_number: The sequence of the block in the trigger model
        :param delay: The amount of time in seconds to delay (167 ns to 10 ks;
        0 for no delay)
        """
        self.write("TRIG:BLOC:DEL:CONS %d, %f" % (block_number, delay))

    def trigger_bloc_delay_external_trigger(
            self, block_number: int,
            clear_mode: Literal["enter", "never"] = "never"):
        """
        This command defines a trigger model block that waits for an event
        before allowing the trigger model to continue.

        ==================  ====================================================
        clear_mode          Description
        ==================  ====================================================
        ``enter``           clear previously detected trigger events when
                            entering the wait block
        ``never``           To immediately act on any previously detected
                            triggers and not clear them (default)
        ==================  ====================================================

        :param clear_mode: clear previously detected trigger or not
        :param block_number: The sequence of the block in the trigger model
        """
        self.write(":TRIG:BLOCk:WAIT %d, EXTernal, %s" %
                   (block_number, clear_mode))

    def trigger_bloc_delay_command_trigger(
            self, block_number: int,
            clear_mode: Literal["enter", "never"] = "never"):
        """
        This command defines a trigger model block that waits for an event
        before allowing the trigger model to continue. It waits for a command
        interface trigger (*TRG):
        ==================  ====================================================
        clear_mode          Description
        ==================  ====================================================
        ``enter``           clear previously detected trigger events when
                            entering the wait block
        ``never``           To immediately act on any previously detected
                            triggers and not clear them (default)
        ==================  ====================================================

        :param clear_mode: clear previously detected trigger or not
        :param block_number: The sequence of the block in the trigger model
        """
        self.write(":TRIG:BLOCk:WAIT %d, COMMand, %s" %
                   (block_number, clear_mode))

    def trigger_bloc_notify(self, block_number: int, notify_id: int):
        """
        Define a trigger model block that generates a trigger event and
        immediately continues to the next block

        When trigger model execution reaches a notify block, the instrument
        generates a trigger event and immediately continues to the next block.

        Other commands can reference the event that the notify block generates.
        This assigns a stimulus somewhere else in the system. For example, you
        can use the notify event as the stimulus of a hardware trigger line,
        such as a digital I/O line.

        When you call this event, you use the format NOTIFY followed by the
        notify identification number. For example, if you assign notify_id as 4,
        you would refer to it as NOTIFY4 in the command that references it.

        :param block_number: The sequence of the block in the trigger model
        :param notify_id: The identification number of the notification; 1 to 8
        """
        self.write(":TRIG:BLOC:NOT %d, %d" % (block_number, notify_id))

    def trigger_bloc_measurement(
            self, block_number: int,
            buffer_name: str = "defbuffer1",
            count: Union[int, str] = 1):
        """
        This block triggers measurements based on the measure function that is
        selected when the trigger model is initiated. When trigger model
        execution reaches this block:
            1. The instrument begins triggering measurements.
            2. The trigger model execution waits for the measurement to be made.
            3. The instrument processes the reading and places it into the
            specified reading buffer.

        If you are defining a user-defined reading buffer, you must create it
        before you define this block. When you set the count to a finite value,
        trigger model execution does not proceed until all operations
        are complete.

        The count parameter can be :
            - A specific integer value (default is ``1`` if nothing set)
            - Infinite (run continuously until stopped): ``INF``
            - Stop infinite to stop the count: ``0``
            - Use most recent count value (default): ``AUTO``

        If you set the count to infinite, the trigger model executes subsequent
        blocks when the measurement is made; the triggering of measurements
        continues in the background until the trigger model execution reaches
        another measure/digitize block or until the trigger model ends. To use
        infinite, there must be a block after the measure/digitize block in the
        trigger model, such as a wait block. If there is no subsequent block,
        the trigger model stops, which stops measurements.

        When you set the count to auto, the trigger model uses the count value
        that is active for the selected function instead of a specific value.
        You can use this with configuration lists to change the count value
        each time a measure/digitize block is encountered.

        :param block_number: The sequence of the block in the trigger model

        :param buffer_name: The name of the buffer,
        if no buffer is defined, ``defbuffer1`` is used

        :param count: Specifies the number of readings to make before moving
        to the next block in the trigger model
        """

        # the TRIG:BLOCK:MEAS is used instead TRIG:BLOCK:MDIG to
        # be compatible with alder firmware version
        self.write(':TRIG:BLOC:MEAS %d, "%s", %s' %
                   (block_number, buffer_name, count))

    def trigger_external_in_edge(self) -> str:
        """
        This command return the type of edge that is detected as an input
        on the external trigger in line

        ==================  ====================================================
        Edge                Description
        ==================  ====================================================
        ``falling``         Detects falling-edge triggers as input
        ``rising``          Detects rising-edge triggers as inpu
        ``either``          Detects rising- or falling-edge triggers as input
        ==================  ====================================================

        :return: The edge type
        """
        return str(self.ask(":TRIG:EXT:IN:EDGE?")).lower()

    def set_trigger_external_in_edge(self, edge: Literal['falling', 'rising', 'either']):
        """
        This command return the type of edge that is detected as an input on the
         external trigger in line

        ==================  ====================================================
        Edge                Description
        ==================  ====================================================
        ``falling``         Detects falling-edge triggers as input
        ``rising``          Detects rising-edge triggers as inpu
        ``either``          Detects rising- or falling-edge triggers as input
        ==================  ====================================================

        :return: The edge type
        """
        edge_type = {'falling': 'FALL', 'rising': 'RIS', 'either': 'EITH'}
        return self.write(":TRIG:EXT:IN:EDGE %s" % edge_type[edge])

    def trigger_external_out_stimulus(self) -> str:
        """
        This command return the event that causes a trigger to be asserted on
        the external output line.

        ==================  ====================================================
        stimulus            Description
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
        This command set the event that causes a trigger to be asserted on the
        external output line.

        ==================  ====================================================
        stimulus            Description
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

    def set_trigger_external_out_logic(
            self, logic_type: Literal["positive", "negative"]):
        """
        This command sets the output logic of the trigger event generator to
        positive or negative for the external I/O out line.

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

    def set_trigger_digital_out_logic(
            self, line_nb: int, logic_type: Literal["positive", "positive"]):
        """
        This command sets the output logic of the trigger event generator
        to positive or negative for the specified line.
        The line must be in trigger mode.

        ==================  ===========================
        logic Type          Description
        ==================  ===========================
        ``positive``        Assert a TTL-high pulse
        ``negative``        Assert a TTL-low pulse
        ==================  ===========================

        :param logic_type: The output logic of the trigger generator
        :param line_nb the digital i/o line between 1 and 6
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

    ############################################################################
    #                              Digitize  measurements                      #
    ############################################################################

    def set_digitize_trigger_source(
            self,
            source: Literal["analog trigger", "manual", "external", "timer", "digital io"],
            n: Optional[int] = None) -> None:
        """
        This command sets the instrument to digitize a measurement the next
        time it detects the specified trigger event.

        It forces the instrument to make a digitize measurement the next time it
        detects the specified trigger event. Options for the trigger event
        parameter are listed in the following table.

        ======================= ================================================
        Source                  Description
        ======================= ================================================
        analog trigger          from the analog trigger
        manual                  from a GBIB command
        external                from the external trigger in
        timer                   when the rigger timer ``n`` (1 to 4) expired
        digital io              from line edge detected on digital input
                                line ``n`` (1 to 6)
        ======================= ================================================

        A digitize function must be active before sending this command.
        The measurement is digitized for the active function. If a measure
        function is active, an error is generated. Before using this command,
        set the active reading buffer. Readings are stored in the active
        reading buffer.

        If the count is set to more than 1, the first reading is initialized by
        this trigger. Subsequent readings occur as rapidly as the instrument can
        make them. If a trigger occurs during the group measurement, the trigger
        is latched and another group of measurements with the same count will be
        triggered after the current group completes.

        If the stimulus is set to none, this command has no effect on readings
        """

        if source in ["timer", "digital io"]:
            self.write(":TRIG:DIG:STIM %s" %
                       (self.DIGITIZE_SOURCE_TRIGGER[source] % n))
        else:
            self.write(":TRIG:DIG:STIM %s" % self.DIGITIZE_SOURCE_TRIGGER[source])

    def set_digitize_count(
            self, count: Union[int, Literal['default', 'minimum', 'maximum']]) -> None:
        """
        This command sets the number of measurements to digitize when a
        measurement is requested

        :param count: The number of measurements (1 to 55'000'000) or 'default',
        'minimum' or 'maximum'
        """

        self.write("DIG:COUN %s" % str(count))

    def set_digitize_function(self, function: Literal["current", "voltage"]):
        """ This command selects which digitize function is active. """
        self.write("DIG:FUNC \"%s\"" % function)

    def digitize_read_measurement(
            self, buffer_name: str = 'defbuffer1',
            buffer_elements: Union[TraceDataOption, Sequence[TraceDataOption]] = ('reading',)):
        """
        This command makes a digitize measurement, places it in a reading buffer

        You must set the instrument to a digitize function before sending this
        command. This query makes the number of readings specified by
        set_digitize_count().

        To get multiple readings, use the trace_data() function.

        When specifying buffer elements, you can:
            - Specify buffer elements in any order.
            - Include up to 13 elements in a single list. You can repeat
            elements as long as the number of elements in the list is less
            than 13

            =============== ====================================================
            elements        description
            =============== ====================================================
            date            The date when the data point was measured; the
                            buffer style must be set to the style standard or
                            full to use this option

            extra           Returns an additional value (such as the sense
                            voltage from a DC voltage ratio measurement);
                            the reading buffer style must be set to full to use
                            this option

            extraformatted  Returns the measurement and the unit of measure of
                            additional values; the reading buffer style must be
                            set to full to use this option

            extraunit       Returns the units of additional values; the reading
                            buffer style must be set to full to use this option

            formatted       The measured value as it appears on the front panel

            fractional      The fractional seconds when the data point was
                            measured

            reading         The measurement reading

            relative        The relative time when the data point was measured

            seconds         The seconds in UTC (Coordinated Universal Time)
                            format when the data point was measured

            status          The status information associated with the
                            measurement; see the "Buffer status bits for sense
                            measurements" table below

            time            The time when the data point was measured

            tstamp          The timestamp when the data point was measured

            unit            The unit of measure of the measurement
            =============== ====================================================
        """

        if not isinstance(buffer_elements, abc.Sequence):
            buffer_elements = [buffer_elements]

        element_list = ", ".join(str(self.TRACE_DATA_OPTION[el]) for el in buffer_elements)

        self.write(":READ:DIG? \"%s\", %s " % (buffer_name, element_list))

    ############################################################################
    #                             digit i/o                                    #
    ############################################################################
    def set_digital_io_mode(
            self, line_nb: int, line_type: Literal["digital", "trigger"],
            line_direction: Literal["in", "out"]):
        """
        This command sets the mode of the digital I/O line to be a digital line,
        trigger line,or synchronous line and sets the line to be input, output,
        or open-drain.

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
    #                               trace                                      #
    ############################################################################

    def trace_data(
            self, start_index: int, stop_index: int,
            buffer_elements: Union[TraceDataOption, Iterable[TraceDataOption]] = ("reading",),
            buffer_name: str = "defbuffer1"
    ) -> Union[list[float | str], list[tuple[str, ...]]]:
        """
        This command returns specified data elements from a specified reading
        buffer

        The options for 'buffer_name' are described in the following table

        =============== ========================================================
        elements        description
        =============== ========================================================
        date            The date when the data point was measured; the buffer
                        style must be set to the style standard or full to use
                        this option

        extra           Returns an additional value (such as the sense voltage
                        from a DC voltage ratio measurement); the reading buffer
                        style must be set to full to use this option

        extraformatted  Returns the measurement and the unit of measure of
                        additional values; the reading buffer style must be set
                        to full to use this option

        extraunit       Returns the units of additional values; the reading
                        buffer style must be set to full to use this option

        formatted       The measured value as it appears on the front panel

        fractional      The fractional seconds when the data point was measured

        reading         The measurement reading

        relative        The relative time when the data point was measured

        seconds         The seconds in UTC (Coordinated Universal Time) format
                        when the data point was measured

        status          The status information associated with the measurement;
                        see the "Buffer status bits for sense measurements"
                        table below

        time            The time when the data point was measured

        timestamp       The timestamp when the data point was measured

        unit            The unit of measure of the measurement
        =============== ========================================================

        .. Warning
            because of  GPIB limitation, it is unadvised to retrieve more
            than 200 values at each request

        :param start_index: Beginning index of the buffer to return;
        must be 1 or greater

        :param stop_index: Ending index of the buffer to return

        :param buffer_name: A string that indicates the reading buffer if no
        buffer is specified, ``defbuffer1`` is used

        :param buffer_elements: A list of elements in the buffer to print;
        if nothing is specified, ``reading`` is used

        :return if buffer_elements is a string, return a list of float if
        buffer_elements is ``reading`` and a list of str otherwise.
        If buffer_elements is an Iterable a list of len(buffer_elements)
        element for each buffer line

        """
        if isinstance(buffer_elements, str):
            buffer_elements = [buffer_elements]

        element_list = ", ".join(self.TRACE_DATA_OPTION[el] for el in buffer_elements)

        res = self.ask("TRACe:DATA? %d, %d, \"%s\", %s" %
                       (start_index, stop_index, buffer_name, element_list))

        if len(buffer_elements) == 1 and buffer_elements[0] == "reading":
            return list(map(float, res.split(",")))

        else:
            res_list = res.split(",")
            return list(zip(
                *[res_list[i::len(buffer_elements)]
                  for i in range(len(buffer_elements))]
            ))

    def trace_clear(self, buffer_name: str = "defbuffer1"):
        """
        This command clears all readings and statistics from
        the specified buffer.

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
        This command contains the number of readings in the specified
         reading buffer.

        :param buffer_name: A string that indicates the reading buffer,
        if no buffer is specified, ``defbuffer1`` is used

        :return:  number of readings in the buffer
        """
        return int(self.ask(":TRACe:ACTual? \"%s\"" % buffer_name))

    def trace_max_size(self, buffer_name: str = "defbuffer1"):
        """
        This command contains the number of readings in the specified
        reading buffer.

        :param buffer_name: A string that indicates the reading buffer,
        if no buffer is specified, ``defbuffer1`` is used

        :return:  maximum number of readings in the buffer
        """
        return int(self.ask(":TRACe:POINts? \"%s\"" % buffer_name))

    def set_trace_max_size(self, new_size, buffer_name: str = "defbuffer1"):
        """
        This command allows you to change or view how many readings a buffer
        can store. Changing the size of a buffer will cause any existing
        data in the buffer to be lost.

        If you select 0, the instrument creates the largest reading buffer
        possible based on the available memory when the buffer is created.

        The overall capacity of all buffers stored in the instrument can be up
        to 7 500 000 readings for standard reading buffers and 20 000 000 for
        compact reading buffers

        :param buffer_name: A string that indicates the reading buffer,
        if no buffer is specified, ``defbuffer1`` is used

        :param new_size: the wanted buffer maximum size
        """
        self.write(":TRACe:POINts %d, \"%s\"" % (new_size, buffer_name))

    def set_trace_fill_mode(self, fill_type: str, buffer_name: str = "defbuffer1"):
        """
        This command determines if a reading buffer is filled continuously
        or is filled once and stops

        When a reading buffer is set to fill once, no data is overwritten
        in the buffer. When the buffer is filled, no more data is stored in
        that buffer and new readings are discarded.

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
        This command determines if a reading buffer is filled continuously or is
        filled once and stops

        When a reading buffer is set to fill once, no data is overwritten in
        the buffer. When the buffer is filled, no more data is stored in that
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
        if no buffer is specified

        :return ``continuous`` or ``once``
        """
        return self.write(":TRACe:FILL:MODE %s \"%s\"" % buffer_name).lower()

    def trace_make(
            self, buffer_name: str, size: int,
            style: Literal["compact", "standard", "full", "writable", "fullwritable"] = "standard"):
        """
        This command creates a user-defined reading buffer.

        The buffer name for a user-defined reading buffer cannot be defbuffer1
        or defbuffer2. In addition, the buffer name must not already exist as
        a global variable, a local variable, table or array.

        When you create a reading buffer, it becomes the active buffer.
        If you create two reading buffers, the last one you create becomes
        the active buffer.

        If you select 0, the instrument creates the largest reading buffer
        possible based on the available memory when the buffer is created.
        (only with the last firmware version)

        Once you store the first reading in a compact buffer, you cannot
        change certain measurement settings, including range, display digits,
        and units; you must clear the buffer first. Not all remote commands are
        compatible with the compact, writable, and full writable buffer styles.
        Check the Details section of the command descriptions before using them
        with any of these buffer styles.

        Writable reading buffers are used to bring external data into the
        instrument. You cannot assign them to collect data from the instrument.

        =============== ========================================================
        style           description
        =============== ========================================================
        compact         Store readings with reduced accuracy with no formatting
                        information, 1 μs accurate timestamp
        standard        Store readings with full accuracy with formatting
        full            Store the same information as standard, plus additional
                        information
        writable        Store external reading buffer data
        fullwritable    Store external reading buffer data with two
                        reading values
        =============== ========================================================

        :param buffer_name: a string that indicates the name of the buffer
        :param size: A number that indicates the maximum number of readings
        that can be stored
        :param style: The type of reading buffer to create:
        """
        self.write("TRACe:MAKE \"%s\" %d %s" % (buffer_name, size, style))

    ############################################################################
    #                               Measurement                                #
    ############################################################################

    def range(self, function: Optional[FunctionType] = None):
        """
        Return the range for the function

        The range is return in float in the principal unit with no subunit
        (e.g. A, V, Ω or F). If ``function`` is ``None``, the function will
        use the function in which the tool already is.

        The available ranges are:

        ======================  ================================================
        function                ranges
        ======================  ================================================
        current dc              10µA, 100µA, 1mA, 10mA, 100mA, 1A, 3A

        current ac              1mA, 10mA, 100mA, 1A, 3A

        voltage ac              100mV, 1V, 10V, 100V, 1000V

        voltage dc              100mV, 1V, 10V, 100V, 700V

        resistance              10Ω, 100Ω, 1kΩ, 10kΩ, 100kΩ, 1MΩ, 10MΩ,
                                100MΩ, 1GΩ

        resistance 4W           1Ω, 10Ω, 100Ω, 1kΩ, 10kΩ, 100kΩ, 1MΩ,
                                10MΩ, 100MΩ, 1GΩ

        capacitance             1nF, 10nF, 100nF, 1µF, 10µF, 100µF, 1mF
        ======================  ================================================

        :param function: The function to which the setting is return
        """

        return float(self.ask(":SENS:%s:RANG?" % self._function_gpib_code(function)))

    def set_range(self, new_range: float, function: Optional[FunctionType] = None):
        """
        set the range for the function

        If ``function`` is ``None``, the function will use the function in which
        the tool already is. The available ranges are:

        ======================  ================================================
        function                ranges
        ======================  ================================================
        current dc              10µA, 100µA, 1mA, 10mA, 100mA, 1A, 3A

        current ac              1mA, 10mA, 100mA, 1A, 3A

        voltage ac              100mV, 1V, 10V, 100V, 1000V

        voltage dc              100mV, 1V, 10V, 100V, 700V

        resistance              10Ω, 100Ω, 1kΩ, 10kΩ, 100kΩ, 1MΩ, 10MΩ,
                                100MΩ, 1GΩ

        resistance 4W           1Ω, 10Ω, 100Ω, 1kΩ, 10kΩ, 100kΩ, 1MΩ,
                                10MΩ, 100MΩ, 1GΩ

        capacitance             1nF, 10nF, 100nF, 1µF, 10µF, 100µF, 1mF
        ======================  ================================================

        :param new_range: the new range set
        :param function: The function to which the setting is set
        """
        self.write(":SENS:%s:RANG %s" % (self._function_gpib_code(function), new_range))

    def set_auto_range(self, function: Optional[FunctionType] = None):
        """
        Sets the active function to use auto-range, or can set it for
        another function.

        If ``function`` is ``None``, the function will use the function in which
        the tool already is. The function can be : current dc, current ac,
        voltage ac, voltage dc, resistance, resistance 4W, capacitance

        :param function: A valid function name, or None for the active function
        """
        self.write(":SENS:%s:RANG:AUTO 1" % self._function_gpib_code(function))

    def nplc(self, function: Optional[FunctionType] = None):
        """
        This command get the time that the input signal is measured for the
         selected function. If ``function`` is ``None``, the function will
         use the function in which the tool already is.

        **Available function:**
            current dc, current ac, voltage ac, voltage dc, resistance, resistance 4W, diode, temperature

        **Note**
            at 60Hz line power frequency the maximum is 10

        :param function: The function to which the setting is get
        """

        return float(self.ask(":SENS:%s:NPLC?" % self._function_gpib_code(function)))

    def set_nplc(self,
                 new_nplc: Union[float, str],
                 function: Optional[FunctionType] = None):
        """
        This command sets the time that the input signal is measured for the
        selected function. If ``function`` is ``None``, the function will use
        the function in which the tool already is.

        **Available function:**
        current dc, current ac, voltage ac, voltage dc, resistance,
        resistance 4W, diode, temperature

        **Note**
        The NPLC is a float between 0.0005 and 12 (at 50Hz) or 10 (at 60Hz)
        can also be ``def``, ``min`` or ``max`` for default, minimum and
        maximum value

        :param new_nplc: The number of power-line cycles per measurement:
        0.0005 to 12 or ``def``, ``min`` or ``max``

        :param function: The function to which the setting is set
        """

        self.write(":SENS:%s:NPLC %s" % (self._function_gpib_code(function), new_nplc))
        if new_nplc < 1:
            time.sleep(1)

    def set_line_sync(self, on_off: Union[bool, str],
                      function: Optional[FunctionType] = None):
        """
        This command determines if line synchronization is used during the
         measurement.

        **Available function:**
        current dc, voltage dc, resistance, resistance 4W, temperature

        :param on_off: True or ``on`` or False or ``off``
        :param function: The function to which the setting is set
        """

        self.write(":SENS:%s:LINE:SYNC %s" %
                   (self._function_gpib_code(function), self.__is_on_off(on_off)))

    def aperture(self, function: Optional[FunctionType] = None):
        """
        This command queries the aperture setting for the selected function.
        If ``function`` is ``None``, the function will use the function in which
        the tool already is.

        **Available function:**
        current dc, current ac, voltage ac, voltage dc, resistance,
        resistance 4W, diode, temperature, frequency, period

        :param function: The function to which the setting is get
        """
        return float(self.ask(":SENS:%s:APER?" % self._function_gpib_code(function)))

    def set_sample_rate(
            self,
            sample_rate: Union[int, Literal['minimum', 'maximum', 'default']],
            function: Literal['voltage', 'current']):
        """
        This command defines the precise acquisition rate at which the
        digitizing measurements are made.

        :param sample_rate: 1'000 to 1'000'000 readings per second
        :param function: The function to which the setting is get
        """

        if isinstance(sample_rate, (float, int)):
            sample_rate = '%d' % sample_rate

        if function.lower().strip() == 'voltage':
            function = 'DIGitize:VOLTage'
        else:
            function = 'DIGitize:CURRent'

        self.write(":SENS:%s:SRATE %s" % (function, sample_rate))

    def set_aperture(
            self,
            new_aperture: Union[float, str],
            function: Optional[FunctionType] = None):
        """
        This command sets the time that the input signal is measured for the
        selected function. If ``function`` is ``None``, the function will use
        the function in which the tool already is.

        **Available function:**
        current dc, current ac, voltage ac, voltage dc, resistance,
        resistance 4W, diode, temperature, frequency and Period

        **Aperture value**
        is a float in the range define in the table or can also be ``def``,
        ``min`` or ``max`` for default minimum and maximum value

        ======================  =======================  ===================
        Function                Default value             Range
        ======================  =======================  ===================
        Voltage (AC and DC)     60 Hz: 16.67 ms          8.333 μs to 0.25 s
                                50 Hz: 20 ms             10 μs to 0.24 s

        Current (AC and DC)     60 Hz: 16.67 ms          8.333 μs to 0.25 s
                                50 Hz: 20 ms             10 μs to 0.24 s

        Resistance (2 or 4W)    60 Hz: 16.67 ms          8.333 μs to 0.25 s
                                50 Hz: 20 ms             10 μs to 0.24 s

        Diode                   60 Hz: 16.67 ms          8.333 μs to 0.25 s
                                50 Hz: 20 ms             10 μs to 0.24 s

        Temperature             60 Hz: 16.67 ms          8.333 μs to 0.25 s
                                50 Hz: 20 ms             10 μs to 0.24 s

        Frequency and Period    10 ms                    10 ms to 273 ms
        ======================  =======================  ===================

        :param new_aperture: he time of the aperture; or ``def``, ``min`` or ``max``
        :param function: The function to which the setting is set
        """

        self.write(":SENS:%s:APER %s" %
                   (self._function_gpib_code(function), new_aperture))

    def set_detector_bandwidth(
            self, function: [FunctionType], bandwidth: str = "DEF"):
        """
        This function sets the detector bandwidth to improve measurement
        accuracy. Select the bandwidth that contains the lowest frequency
        component of the input signal. For example, if the lowest frequency
        component of your input signal is 40 Hz, use a bandwidth setting
        of 30 Hz.

        If the bandwidth is set to 3 Hz or 30 Hz, the autozero feature is always
        enabled and the integration unit is set to Sampling. In addition,
        the Sampling Time is displayed.

        :param function: The function to which the setting is set
        (For AC measurements only)
        :param bandwidth: The bandwidth that should be used; or ``DEF``(30 Hz),
        ``MIN``(3 Hz) or ``MAX``(300 Hz)
        """
        if function in ['voltage ac', 'current ac'] and bandwidth in ["DEF", "MIN", "MAX"]:
            self.write(":%s:DET:BAND %s" % (self.FUNCTION[function], bandwidth))

    def read_measurement(
            self,
            buffer_elements: TraceDataOption = "reading",
            buffer_name: str = 'defbuffer1'):
        """
        This command makes measurements, places them in a reading buffer, and
        returns the last reading.

        The options for 'buffer_elements' are described in the following table

       ====================  ===================================================
       buffer_elements       Description
       ====================  ===================================================
       ``reading``           The measurement reading
        ``relative``         The relative time when the data point was measured
        ``date``             The buffer style must be set to the style standard
                             or full to use this option
        ``seconds``          The seconds in UTC format when the data point was
                             measured
        ``time``             The time when the data point was measured
        ``timestamp``        The timestamp when the data point was measured
       ====================  ===================================================

        :param buffer_name: A string that indicates the reading buffer,
        if no buffer is specified, ``defbuffer1`` is used

        :param buffer_elements: A list of elements in the buffer to print;
        if nothing is specified, ``reading`` is used

        :return a float if buffer_elements is reading, a st otherwise
        """
        res = self.ask("READ? \"%s\", %s" %
                       (buffer_name, self.TRACE_DATA_OPTION[buffer_elements]))

        if buffer_elements == "reading":
            return float(res)
        else:
            return res

    ############################################################################
    #                                utilities                                 #
    ############################################################################

    def __init__(self, adapter, **kwargs):
        super(Keithley7510, self).__init__(adapter,
                                           "Keithley 7510 Multimeter", **kwargs)

    def trigger(self):
        self.write('*TRG')

    def errors_clear(self):
        self.write(":SYST:CLE")
        self.write(":DISP:CLE")
        self.write(":DISP:SCR HOME")

    def check_errors(self):
        """ Read all errors from the instrument."""
        errmsg = ""
        while True:
            err = self.ask(":SYST:ERR?")
            if "no error" not in err.lower():
                errmsg += "Keithley 7510: %s \n" % err
            else:
                break

        return errmsg

    def reset(self):
        """ Resets the instrument state. """
        self.write("*RST;")
        self.write("*CLS;")
        self.write(":STAT:CLE;")
        self.write(":STAT:PRES;")
        self.write(":SYST:CLE;")

    def beep(self, frequency, duration):
        """
        Sounds a system beep.

        :param frequency: A frequency in Hz between 65 Hz and 2 MHz
        :param duration: A time in seconds between 0 and 7.9 seconds
        """
        self.write(":SYST:BEEP %g, %g" % (frequency, duration))

    def digits(self, function=None):
        """
        An property that controls the number of digits
        readings, which can a discrete values from 3 to 7 or 'DEF' for default,
        'MIN' for minimum or 'MAX' for maximum.
        """

        prec = self.ask(":FORM:ASC:PREC?")
        dig = self.ask(":DISP:" + self._function_gpib_code(function) + ":DIG?")
        return min(prec, dig)

    def set_digits(self, digit='DEF', function=None):
        """
        A property that controls the number of digits
        readings, which can a discrete values from 3 to 7 or 'DEF' for default,
        'MIN' for minimum or 'MAX' for maximum. """

        if digit in [3, 4, 5, 6, 7, 'DEF', 'MAX', 'MIN']:
            cmd = ":FORMat:ASCii:PREC %s;:DISP:%s:DIG %s" % \
                  (digit, self._function_gpib_code(function), digit)
            self.write(cmd)
