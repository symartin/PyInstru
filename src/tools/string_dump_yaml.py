
#
# This file is part of the PyInstru package,
# parts of the code is based on ruamel.yaml package.
#
# Copyright (c) 2019-2023 Sylvain Martin
# Copyright (c) 2014-2023 Anthon van der Neut, Ruamel bvba




import collections.abc
from ruamel.yaml import StringIO, YAML, ruamel


class StringDumpYaml(YAML):
    """
    Subclassing in order to get a monolithic string representation of the stream
    back. It is allowing backward compatibility with old yamel library
    https://yaml.readthedocs.io/en/latest/example.html#output-of-dump-as-a-string
    """

    def __init__(self, **kwarg):
        super().__init__(**kwarg)
        self.width = 4096

    def dump(self, data, stream=None, **kw):

        inefficient = False
        if stream is None:
            inefficient = True
            stream = StringIO()
        YAML.dump(self, self._flow_list(data), stream, **kw)
        if inefficient:
            return stream.getvalue()

    @staticmethod
    def _flow_list(obj):
        """ to have dictionary in block style and list in flow style """
        _fl = StringDumpYaml._flow_list

        if isinstance(obj, dict):
            for key, value in obj.items():
                obj[key] = _fl(value)

        elif isinstance(obj, collections.abc.Sequence) and not isinstance(obj, str):
            obj = ruamel.yaml.CommentedSeq([_fl(sub_obj) for sub_obj in obj])
            obj.fa.set_flow_style()  # fa -> format attribute

        return obj