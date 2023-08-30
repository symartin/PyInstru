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
from .string_dump_yaml import StringDumpYaml


def load_metadata(filepath: str = "") -> dict:
    """
    load the metadata from a datafile at filepath and return a dictionary with
    the metadata

    :param filepath: the path to the datafile
    :return: a dictionary with the metadata
    """

    str_yaml = StringDumpYaml()  # default, if not specified, is 'rt' (round-trip)
    str_yaml.default_flow_style = False

    with open(filepath) as f:
        lines = ""

        for raw_line in f:
            if raw_line[0].strip() != "#": break

            line = raw_line[1:].replace("\t", "    ")
            lines = lines + line

    return str_yaml.load(lines)
