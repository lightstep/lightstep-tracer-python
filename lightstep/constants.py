"""Constants"""

# Runtime constants
FLUSH_THREAD_NAME = 'Flush Thread'
FLUSH_PERIOD_SECS = 2.5
DEFAULT_MAX_SPAN_RECORDS = 1000

# Reserved Span keys
PARENT_SPAN_GUID = 'parent_span_guid'

# Log Keywords
PAYLOAD = 'payload'
SPAN_GUID = 'span_guid'

# Log Levels
INFO_LOG = 'I'
WARN_LOG = 'W'
ERROR_LOG = 'E'
FATAL_LOG = 'F'

# JSON pickle settings
JSON_FAIL = '<Invalid Payload'
JSON_MAX_DEPTH = 32
JSON_UNPICKLABLE = True
JSON_WARNING = True

# utils constants
SECONDS_TO_MICRO = 1000000

# Recorder constants
MAX_LOG_MEMORY = 1024
MAX_LOG_LEN = 984
JOIN_ID_TAG_PREFIX = "join:"
