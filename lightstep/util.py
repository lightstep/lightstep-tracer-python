""" Utility functions
"""
import random
import time
import constants

guid_rng = random.Random()   # Uses urandom seed

def _collector_url_from_hostport(secure, host, port):
    """
    Create an appropriate collector URL given the parameters.

    `secure` should be a bool.
    """
    if secure:
        protocol = 'https://'
    else:
        protocol = 'http://'
    return ''.join([protocol, host, ':', str(port), '/_rpc/v1/reports/binary'])

def _generate_guid():
    """
    Construct a guid - a random 64 bit integer
    """
    return guid_rng.getrandbits(64) - 1

def _id_to_hex(id):
    return '{0:x}'.format(id)

def _now_micros():
    """
    Get the current time in microseconds since the epoch.
    """
    return _time_to_micros(time.time())

def _time_to_micros(t):
    """
    Convert a time.time()-style timestamp to microseconds.
    """
    return long(round(t * constants.SECONDS_TO_MICRO))

def _merge_dicts(*dict_args):
    """Destructively merges dictionaries, returns None instead of an empty dictionary.

    Elements of dict_args can be None.
    Keys in latter dicts override those in earlier ones.
    """
    result = {}
    for dictionary in dict_args:
        if dictionary:
            result.update(dictionary)
    return result if result else None

def _coerce_str(str_or_unicode):
    if isinstance(str_or_unicode, str):
        return str_or_unicode
    elif isinstance(str_or_unicode, unicode):
        return str_or_unicode.encode('utf-8', 'replace')
    else:
        try:
            return str(str_or_unicode)
        except Exception:
            # Never let these errors bubble up
            return '(encoding error)'
