# filters

import re # for fix_bill_id

from billy.importers.filter import register_filter

@register_filter
def strip_bookend_spaces(argument):
    """
    Strip leading and tailing space from the string.
    """
    return argument.strip()

_bill_id_re = re.compile(r'([A-Z]*)\s*0*([-\d]+)')

@register_filter
def fix_bill_id(bill_id):
    """
    Fix the bill ID.
    """
    bill_id = bill_id.replace('.', '')
    return _bill_id_re.sub(r'\1 \2', bill_id).strip()

@register_filter
def remove_newlines(blob):
    return re.sub('\s+', ' ', blob)
