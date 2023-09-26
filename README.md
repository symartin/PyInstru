# PyInstru: Scientific instrument drivers

## Status: Archived
This repository has been archived and is no longer maintained.

![status: inactive](https://img.shields.io/badge/status-inactive-red.svg)
[![GitHub license](https://img.shields.io/github/license/symartin/PyInstru.svg)](https://raw.githubusercontent.com/symartin/PyInstru/main/LICENSE)

## Description
[![Made with love in Python](https://img.shields.io/badge/Made_with_♥️_in_Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://github.com/symartin/PyInstru)

Set of scientific instrument drivers used for low-noise e-test for the 
microelectronic. The code is originally based on code based on the 
[PyMeasure](https://github.com/ralph-group/pymeasure) structure but deviated significantly. 

## Compatible Instruments

Obviously, not all the possible commands (GPIB or other) are implemented, but the main ones are:

- [Keithley 7510](https://www.tek.com/en/products/keithley/digital-multimeter/dmm7510) Digit Graphical Sampling Multimeter
- [Keithley 2450](https://www.tek.com/en/datasheet/smu-2400-graphical-sourcemeter/model-2450-touchscreen-source-measure-unit-smu-instrument) Source Measure Unit (SMU)
- [Active Technologies PG-1074 & PG-1072](https://www.activetechnologies.it/products/signal-generators/pulse-generators/pg-1000/) pulse generator (rev.A)
- [Agilent Pulse generator 81110A](https://www.keysight.com/us/en/product/81110A/pulse-pattern-generator-165-330mhz.html)
- [USB-xSPDT-A18](https://www.minicircuits.com/WebStore/dashboard.html?model=USB-2SPDT-A18) MiniCircuit RF switch 
- [Tektronix 70000](https://www.tek.com/en/products/arbitrary-waveform-generators/awg70000) AWG
- [ixBlue DrVe10Mo](https://www.ixblue.com/store/dr-ve-10-mo) RF amplifier
- [Keysight DSOX6000](https://www.keysight.com/us/en/products/oscilloscopes/infiniivision-2-4-channel-digital-oscilloscopes/infiniivision-6000-x-series-oscilloscopes.html) digital oscilloscope series
- [Keysight 33500B](https://www.keysight.com/us/en/products/waveform-and-function-generators/trueform-series-waveform-and-function-generators.html) AWG series

## Setup and packages requirement

### Python and packages requirement

The code is written for python *64 bit* 3.10.x. It also needs some packages 
that one can find in the requirement.txt.

One can install those package by doing :
```shell script
python -m pip install -r requirements.txt
```

In addition, do not install the ``visa`` package in the same environment, there 
is a conflict with ``PyVisa``.

###  NI-DAQmx driver
to be able to control the DAC the DAQmx drivers are needed. They can be  downloaded 
[her](https://www.ni.com/fr-fr/support/downloads/drivers/download.ni-daqmx.html)

### Set up the MiniCircuit Mechanical RF Switch Boxes

To command the Minicircuit RF Switch, it also needs additional drivers provide 
by MiniCircuit. One can find the complete documentation 
[here](https://www.minicircuits.com/softwaredownload/Prog_Manual-2-Switch.pdf)

1. Download the drivers [here](https://www.minicircuits.com/softwaredownload/rfswitchcontroller.html)  
2. This library use the .net implementation:

    - Copy mcl_RF_Switch_Controller_NET45.dll file in C:\WINDOWS\SysWOW64 
    - Right-click on the DLL file in the save location and select Properties to 
      check that Windows has not blocked access to the file (check “Unblock” if
      the option is shown)
    - No registration or further installation action is required 

## Code style

this code respect most of the PEP8 (and following) guidance, except for the line 
break at 79 (or 80) characters. The hard-break is at 120 and except for natural
or easy break before 80, the line should break inbetween 80 and 100. (because,
nobody use 12" screen anymore, come-on !). obviously, web link cannot be broke

In addition, one the major problem in coding style is to be coherent with the 
different libraries, which, for historical reasons, have different styles. It is 
clearly the case between the python and the Qt  or the Logging library for 
example. To reconcile those two worlds, It has been chosen to follow library 
guideline over the PEP8 for all related code. 

One can read the following blog explaining this choice and how to implement it : 
 - [Pyqt coding style guidelines](http://bitesofcode.blogspot.com/2011/10/pyqt-coding-style-guidelines.html)
 - [In depth coding guideline](https://bitesofcode.blogspot.com/2011/10/in-depth-coding-guidelines.html)

Finally, the comments follow  [sphinx](https://www.sphinx-doc.org/en/master/index.html) 
style and reStructuredText standard. 

## Licence

- The code coming from [PyMeasure](https://github.com/ralph-group/pymeasure), 
[QCoDeS](https://github.com/QCoDeS/Qcodes) and 
[StringDumpYaml](https://yaml.readthedocs.io/en/latest/example.html#output-of-dump-as-a-string)
were under the MIT Licence at the  time of the integration. 

- This code is under the 
[GPL-3 Licence](https://raw.githubusercontent.com/symartin/PyInstru/main/LICENSE)

## Copyright

- *Copyright (c) 2019-2023 Sylvain Martin* for the main part

- *Copyright (c) 2013-2019 PyMeasure Developers*
for the ``Instrument`` and ``adpater`` class structure

- *Copyright (c) 2015, 2016 by Microsoft Corporation and Københavns Universitet*
for parte of the The Tektronix 70000 driver

- *Copyright (c) 2014-2023 Anthon van der Neut, Ruamel bvba* for the 
StringDumpYaml class

