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
from typing import Literal

from .. import Instrument


log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())


class DSOX6000(Instrument):
    """
    Represents the Keysight DSOX 60000 oscilloscope family.
    """

    def __init__(self, adapter, **kwargs):
        super().__init__(adapter,
                         "DSOX6000 series RF oscilloscope", **kwargs)

    ############################################################################
    #                         measurement commands                             #
    ############################################################################
    def clear_measurements(self) -> None:
        """
        This command clears all selected measurements and markers from the screen.
        """
        cmd = ":MEASure:CLEar"
        log.debug(cmd)
        self.write(cmd)

    def set_measurement_positive_pulse_width(self, channel: int = 1) -> None:
        """
        This command installs a screen measurement and starts the
        positive pulse width measurement.

        :param channel: The channel, 1 or 2
        """
        self.write(":MEAS:PWID CHAN%d" % channel)

    def measurement_positive_pulse_width(self, channel: int = 1) -> float:
        """
        Return the width of the displayed positive pulse closest to the trigger
         reference.

        Pulse width is measured at the midpoint of the upper and lower thresholds.

        IF the edge on the screen closest to the trigger is falling:
        THEN width = (time at trailing falling edge - time at leading rising edge)
        ELSE width = (time at leading falling edge - time at leading rising edge)

        :param channel: The channel, 1 or 2
        :return:  the pulse width in s
        """
        return float(self.ask(":MEAS:PWID? CHAN%d" % channel))

    def set_measurement_negative_pulse_width(self, channel: int = 1) -> None:
        """
        The :MEASure:NWIDth command installs a screen measurement and starts a
        negative pulse width measurement.

        :param channel: The channel, 1 or 2
        """
        self.write(":MEAS:NWID CHAN%d" % channel)

    def measurement_negative_pulse_width(self, channel: int = 1):
        """
        Returns the width of the negative pulse on the screen closest
        to the trigger reference using the midpoint between the upper
        and lower thresholds.

        FOR the negative pulse closest to the trigger point:
        width = (time at trailing rising edge - time at leading falling edge)

        :param channel: The channel, 1 or 2
        :return: negative pulse width in s
        """
        return float(self.ask(":MEAS:NWID? CHAN%s" % channel))

    def set_measurement_fall_time(self, channel: int = 1) -> None:
        """
        This command installs a screen measurement and starts a fall-time
        measurement. For highest measurement accuracy, set the sweep speed as
        fast as possible, while leaving the falling edge of the waveform on
        the display.

        :param channel: The channel, 1 or 2
        """
        self.write(":MEAS:FALL CHAN%d" % channel)

    def measurement_fall_time(self, channel: int = 1) -> float:
        """
        Return the fall time of the displayed falling (negative-going) edge
        closest to the timebase reference.

        The fall time is determined by measuring the time at the upper threshold
        of the falling edge, then measuring the time at the lower threshold of
        the falling edge, and calculating the fall time with the following
        formula:

        fall time = time at lower threshold - time at upper threshold

        :param channel: The channel, 1 or 2
        :return: the fall time in s
        """
        return float(self.ask(":MEAS:FALL? CHAN%d" % channel))

    def set_measurement_average(self, channel: int = 1):
        """ installs a screen measurement and starts an
        average value measurement
        """
        self.write(":MEAS:VAVerage DISPlay, CHAN%d" % channel)

    def set_measurement_rise_time(self, channel: int = 1) -> None:
        """
        This command installs a screen measurement and starts a
        rise-time measurement.

        :param channel: The channel, 1 or 2
        """
        self.write(":MEAS:RISE CHAN%d" % channel)

    def measurement_rise_time(self, channel: int = 1) -> float:
        """
        Return the rise time of the displayed rising (positive-going)
        edge closest to the timebase reference.

        For maximum measurement accuracy, set the sweep speed as fast as
        possible while leaving the leading edge of the waveform on the display.
        The rise time is determined by measuring the time at the lower threshold
        of the rising edge and the time at the upper threshold of the rising
        edge, then calculating the rise time with the following formula:

        rise time = time at upper threshold - time at lower threshold

        :param channel: The channel, 1 or 2
        :return: rise time in s
        """
        return float(self.ask(":MEAS:RISE? CHAN%s" % channel))

    def set_measurement_overshoot(self, channel: int = 1) -> None:
        """
        This command installs a screen measurement and starts an
        overshoot measurement.

        :param channel: The channel, 1 or 2
        """
        self.write(":MEAS:OVER CHAN%s" % channel)

    def measurement_overshoot(self, channel: int = 1) -> float:
        """
        Returns the overshoot of the edge closest to the trigger reference,
        displayed on the screen.

        The method used to determine overshoot is to make three different
        vertical value measurements: Vtop, Vbase, and either Vmax or Vmin,
        depending on whether the edge is rising or falling.

        For a rising edge:
        overshoot = ((Vmax-Vtop) / (Vtop-Vbase)) x 100

        For a falling edge:
        overshoot = ((Vbase-Vmin) / (Vtop-Vbase)) x 100

        Vtop and Vbase are taken from the normal histogram of all waveform
        vertical values. The extremum of Vmax or Vmin is taken from the waveform
        interval right after the chosen edge, halfway to the next edge.
        This more restricted definition is used instead of the normal one,
        because it is conceivable that a signal may have more preshoot than
        overshoot, and the normal extremum would then be dominated by the
        preshoot of the following edge

        :param channel: The channel, 1 or 2
        :return: the overshoot in V
        """
        return float(self.ask(":MEAS:OVER? CHAN%d" % channel))

    def set_measurement_preshoot(self, channel: int = 1) -> None:
        """
        This command installs a screen measurement and starts
         a preshoot measurement.
        :param channel: The channel, 1 or 2
        """
        self.write(":MEAS:PRE CHAN%d" % channel)

    def measurement_preshoot(self, channel: int = 1) -> float:
        """
        Returns the preshoot of the edge closest to the trigger, displayed on the screen.

        The method used to determine preshoot is to make three different
        vertical value measurements: Vtop, Vbase, and either Vmin or Vmax,
        depending on whether the edge is rising or falling.

        For a rising edge:
        preshoot = ((Vmin-Vbase) / (Vtop-Vbase)) x 100

        For a falling edge:
        preshoot = ((Vmax-Vtop) / (Vtop-Vbase)) x 100

        Vtop and Vbase are taken from the normal histogram of all waveform
        vertical values. The extremum of Vmax or Vmin is taken from the waveform
        interval right before the chosen edge, halfway back to the previous edge.

        This more restricted definition is used instead of the normal one,
        because it is likely that a signal may have more overshoot than preshoot,
        and the normal extremum would then be dominated by the overshoot of the
        preceding edge.

        :param channel: The channel, 1 or 2
        :return: The preshoot in V
        """
        return float(self.ask(":MEAS:PRE? CHAN%d" % channel))

    def set_measurement_voltage_amplitude(self, channel: int = 1) -> None:
        """
        This command installs a screen measurement and starts a vertical
        amplitude measurement.

        :param channel: The channel, 1 or 2
        """
        self.write(":MEAS:VAMP CHAN%d" % channel)

    def measurement_voltage_amplitude(self, channel: int = 1) -> float:
        """
        Returns the vertical amplitude of the waveform.

        To determine the amplitude, the instrument measures Vtop and
        Vbase, then calculates the amplitude as follows:

        vertical amplitude = Vtop - Vbase

        :param channel: The channel, 1 or 2
        :return: the voltage amplitude
        """
        return float(self.ask(":MEAS:VAMP? CHAN%s" % channel))

    def set_measurement_area(self, channel: int = 1) -> None:
        """
        Installs an area measurement on screen. Area
        measurements show the area between the waveform
        and the ground level

        :param channel: The channel, 1 or 2
        """
        self.write(":MEASure:AREa DISPlay, CHAN%s" % channel)

    def set_measurement_voltage_base(self, channel: int = 1) -> None:
        """
        This command installs a screen measurement and starts a
        waveform base value measurement.

        :param channel: The channel, 1 or 2
        """
        self.write(":MEAS:VBAS CHAN%s" % channel)

    def measurement_voltage_base(self, channel: int = 1) -> float:
        """
        Returns the vertical value at the base of the waveform.

        The base value of a pulse is normally not the same as the minimum value

        :param channel: The channel, 1 or 2
        :return: the voltage base in V
        """
        return float(self.ask(":MEAS:VBAS? CHAN%d" % channel))

    def set_measurement_voltage_max(self, channel: int = 1) -> None:
        """
        This command installs a screen measurement and starts a maximum
        vertical value measurement.

        :param channel: The channel, 1 or 2
        """
        self.write(":MEAS:VMAX CHAN%d" % channel)

    def measurement_voltage_max(self, channel: int = 1) -> float:
        """
        Return the maximum vertical value present on the selected waveform.

        :param channel: The channel, 1 or 2
        :return: the maximum voltage in V
        """

        return float(self.ask(":MEAS:VMAX? CHAN%d" % channel))

    def set_measurement_voltage_min(self, channel: int = 1) -> None:
        """
        This command installs a screen measurement and starts a minimum
        vertical value measurement.

        :param channel: The channel, 1 or 2
        """

        self.write(":MEAS:VMIN CHAN%d" % channel)

    def measurement_voltage_min(self, channel: int = 1) -> float:
        """
        Return the minimum vertical value present on the selected waveform.

        :param channel: The channel, 1 or 2
        :return: the minimum voltage in V
        """
        return float(self.ask(":MEAS:VMIN? CHAN%d" % channel))

    def set_measurement_vpp(self, channel: int = 1) -> None:
        """
        This command installs a screen measurement and starts a vertical
        peak-to-peak measurement.

        :param channel: The channel, 1 or 2
        """
        self.write(":MEAS:VPP CHAN%d" % channel)

    def measurement_vpp(self, channel: int = 1) -> float:
        """
        Return the vertical peak-to-peak value and returns that value.

        The peak-to-peak value (Vpp) is calculated with the following formula:
        Vpp = Vmax - Vmin

        Vmax and Vmin are the vertical maximum and minimum values present on the
        selected source

        :param channel: The channel, 1 or 2
        :return:  vertical peak-to-peak amplitude in V
        """
        return float(self.ask(":MEAS:VPP? CHAN%d" % channel))

    def set_measurement_vtop(self, channel: int = 1) -> None:
        """
        This  command installs a screen measurement and starts a
        waveform top value measurement.

        :param channel: The channel, 1 or 2
        """
        self.write(":MEAS:VTOP CHAN%d" % channel)

    def measurement_vtop(self, channel: int = 1) -> float:
        """
        Returns the vertical value at the top of the waveform.

        The top value of the pulse is normally not the same as the maximum value

        :param channel: The channel, 1 or 2
        :return: vertical value at the top in V
        """
        return float(self.ask(":MEAS:VTOP? CHAN%d" % channel))

    def measurement_results(self) -> list[float]:
        """
        returns the results of the continuously displayed measurements.

        If more than one measurement is running continuously, this return values
        are duplicated for each continuous measurement from the first to last
        (top to bottom) result displayed. Each result returned is separated
        from the previous result by a comma. There is a maximum of 10 continuous
        measurements that can be continuously displayed at a time. When no quick
         measurements are installed, this function returns an empty string.

        When the count for any of the measurements is 0, the value of infinity
        (9.9E+37) is returned for the min, max, mean, and standard deviation

        :return: a list with the results
        """
        # TODO: make a preprocess before returning the value
        self.write(":MEASure:STATistics %s" % 'CURRent')
        res = str(self.ask(":MEAS:RES?"))

        return list(map(float, res.split(",")))

    ############################################################################
    #                                  Trigger                                 #
    ############################################################################

    def set_trigger_mode(self, mode: Literal['edge', 'eburst', 'glitch']) -> None:
        """
        Set the trigger mode. The following trigger mode are available :


        =============   ========================================================
        Mode            Description
        =============   ========================================================
        edge            Edge triggering — identifies a trigger by looking for a
                        specified slope and voltage

        eburst          Nth Edge Burst triggering — lets you trigger on the Nth
                        edge of a burst that occurs after an idle time.

        glitch          Pulse width triggering —  sets the oscilloscope to
                        trigger on a positive pulse or on a negative pulse of
                        a specified width.
        =============   ========================================================

        :param mode: the str name of the wanted mode
        """

        self.write(":TRIG:MODE %s" % mode)

    def set_trigger_edge_source(self, source: Literal['channel1', 'channel2', 'external']):
        """
        Set the trigger source. The following source are available :


        =============   ========================================================
        Mode            Description
        =============   ========================================================
        external        triggers on the rear panel EXT TRIG IN signal.
        channel<n>      trigger on a channel signal <n> can be 1 or 2
        =============   ========================================================

        :param source: the wanted source
        """
        self.write(":TRIG:SOURce %s" % source)

    def set_trigger_edge_slope(self,
                               slope: Literal['negative', 'positive', 'either', 'alternate']):
        """
        Set the command specifies the slope of the edge for the trigger.
        The following mode are available : 'negative', 'positive',
        'either', 'alternate'

        :param slope: the wanted slope
        """
        self.write(":TRIG:slope %s" % slope)

    def set_trigger_edge_level(self, level: float):
        """
        sets the trigger level voltage for the active trigger source.

        :param level: the wanted level
        """
        self.write(":TRIG:level %f" % level)

    def trigger_arm_single(self):
        """ causes the instrument to acquire a single trigger of data.
            This is the same as pressing the Single key on the front panel"""
        self.write(":SING")

    ############################################################################
    #                        Timebase commands                                 #
    ############################################################################

    def set_timebase_scale(self, scale: float):
        """
        This command sets the horizontal scale or units per division for the main window

        :param scale: second per division
        """
        self.write(":TIMebase:SCALe %g" % scale)

    def timebase_scale(self):
        """
        Returns the current horizontal scale setting in
        seconds per division for the main window

        :returns the time per division in s
        """
        return float(self.ask(":TIMebase:SCALe?"))

    def set_timebase_delay(self, delay: float) -> None:
        """
        Sets the time interval between the trigger event and the display
        reference point on the screen.

        :param delay: the delay in s
        """
        self.write(":TIMebase:DELay %g" % delay)

    def timebase_delay(self) -> float:
        """
         returns the current time from the trigger to the display
         reference in seconds.

        :return: the delay in s
        """
        return float(self.ask(":TIMebase:DELay?"))

    def waveform_data(self, channel: int = 1) -> list[float]:
        """
        return the data from the waveform

        do not return the x-axis. use ``waveform_x_increment`` to make the x-axis

        :param channel: The channel, 1 or 2
        :return:a list with the data point
        """
        self.write("WAV:FORM ASC")
        self.write(":WAV:POIN:MODE MAX")
        self.write(":WAVeform:SOURce CHAN%d" % channel)
        res = self.ask(":WAV:DATA?")
        return list(map(float, res[10:].split(',')))

    def waveform_x_increment(self):
        """
        returns the x-increment value for the currently specified source.

        This value is the time difference between consecutive data points
        in seconds.

        :return: time between 2points in s
        """
        return float(self.ask(":WAVeform:XINCrement?"))

    ######################################################################################################
    #                                               Utilities                                            #
    ######################################################################################################

    def shutdown(self):
        self.isShutdown = True
        log.info("Shutting down %s.", self.name)


