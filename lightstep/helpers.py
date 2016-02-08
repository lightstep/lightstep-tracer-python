"""Helper methods for the LightStep tracer.
"""

DEFAULT_CONTEXT_ID_PREFIX = 'open-tracing-context-id-'
DEFAULT_ATTRIBUTE_PREFIX = 'open-tracing-attribute-'

def trace_context_writer(trace_context, trace_context_encoder,
                         context_id_prefix=DEFAULT_CONTEXT_ID_PREFIX,
                         attribute_prefix=DEFAULT_ATTRIBUTE_PREFIX,
                         add=None):
    """Writes trace_context to add() using trace_context_encoder.
    """
    if add is None:
        raise ValueError('add must be set to a function that takes (key, value) as inputs')
    context_id, attributes = trace_context_encoder.trace_context_to_text(trace_context)
    for key, val in context_id.iteritems():
        add(context_id_prefix + key, val)
    if attributes:
        for key, val in attributes.iteritems():
            add(attribute_prefix + key, val)

def trace_context_from_tuples(kv_tuples, trace_context_decoder,
                              context_id_prefix=DEFAULT_CONTEXT_ID_PREFIX,
                              attribute_prefix=DEFAULT_ATTRIBUTE_PREFIX):
    """Produces trace context from input tuples using trace_context_decoder.

    Keys and values will be lowercased to deal with any case-mangling done by the transport layer.
    """
    context_id_prefix, attribute_prefix = context_id_prefix.lower(), attribute_prefix.lower()
    context_id_prefix_len, attribute_prefix_len = len(context_id_prefix), len(attribute_prefix)
    context_id, attributes = {}, {}
    for k, v in kv_tuples:
        key, val = k.lower(), v.lower()
        if key.startswith(context_id_prefix):
            context_id[key[context_id_prefix_len:]] = val
        elif key.startswith(attribute_prefix):
            attributes[key[attribute_prefix_len:]] = val
    return trace_context_decoder.trace_context_from_text(context_id, attributes)
