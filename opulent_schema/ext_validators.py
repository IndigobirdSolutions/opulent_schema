# Some additional validators
import ipaddress
import re

from voluptuous import Invalid


class Hostname:
    # Based on validator from https://github.com/zaggino/z-schema/blob/master/src/FormatValidators.js (MIT)
    REGEX = re.compile(r'^[a-zA-Z](([-0-9a-zA-Z]+)?[0-9a-zA-Z])?(\.[a-zA-Z](([-0-9a-zA-Z]+)?[0-9a-zA-Z])?)*$')

    def __init__(self, msg=None):
        self.msg = msg

    def __call__(self, hostname):
        try:
            if len(hostname) > 255:
                raise ValueError
            if not self.REGEX.match(hostname):
                raise ValueError
            labels = hostname.split('.')
            for label in labels:
                if len(label) > 63:
                    raise ValueError
        except ValueError:
            raise Invalid(self.msg or 'Not a valid hostname')

        return hostname


class IP:
    def __init__(self, version=4, msg=None):
        if version == 4:
            self.cls = ipaddress.IPv4Address
        elif version == 6:
            self.cls = ipaddress.IPv6Address
        else:
            raise ValueError('Not a valid IP version.')
        self.msg = msg

    def __call__(self, value):
        try:
            value = self.cls(value)
        except ValueError:
            raise Invalid(self.msg or 'Not a valid IP address.')
        return str(value)
