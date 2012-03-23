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
def _fix_bill_id(self, bill_id):
    bill_id = bill_id.replace('.', '')
    return _bill_id_re.sub(r'\1 \2', bill_id).strip()

class FixBillID(Filter):
    def __init__(self, keys):
        super(FixBillID, self).__init__()
        self._keys = utils.str_or_list(keys)

    def process_record(self, record):
        for key in self._keys:
            if key in record:
                record[key] = _fix_bill_id(record[key])
        return record

class AltBillFixer(Filter):
    def __init__(self, keys):
        super(AltBillFixer, self).__init__()
        self._keys = utils.str_or_list(keys)

    def process_record(self, data):
        if 'alternate_bill_ids' in data:
            data['alternate_bill_ids'] = [fix_bill_id(bid) for bid in
                                          data['alternate_bill_ids']]
        return data



class BillNormalizerHook(Filter):
    def process_record(self, data):
        bill_votes = votes.pop((data['chamber'], data['session'],
                                    data['bill_id']), [])
        data['votes'].extend(bill_votes)
        return data

class RhodeIslandBillNormalizerHook(Filter):
    def process_record(self, data):
        numeric_bill_id = data['bill_id'].split()[1]
        bill_votes = votes.pop((data['chamber'], data['session'],
                                numeric_bill_id), [])
        data['votes'].extend(bill_votes)
        return data
