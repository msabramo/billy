from saucebrush import utils
from saucebrush.filters import Filter

import re

class UnNewline(Filter):
    def __init__(self, keys):
        super(UnNewline, self).__init__()
        self._keys = utils.str_or_list(keys)

    def _denewline(self, thing):
        return re.sub('\s+', ' ', thing)

    def process_record(self, record):
        for key in self._keys:
            if key in record:
                record[key] = self._denewline(record[key])
        return record

_bill_id_re = re.compile(r'([A-Z]*)\s*0*([-\d]+)')

class FixBillID(Filter):
    def __init__(self, keys):
        super(FixBillID, self).__init__()
        self._keys = utils.str_or_list(keys)

    def _fix_bill_id(self, bill_id):
        bill_id = bill_id.replace('.', '')
        return _bill_id_re.sub(r'\1 \2', bill_id).strip()

    def process_record(self, record):
        for key in self._keys:
            if key in record:
                record[key] = self._fix_bill_id(record[key])
        return record
