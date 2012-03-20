
from saucebrush.emitters import Emitter

class ObjectEmitter(Emitter):
    def __init__(self, output):
        super(ObjectEmitter, self).__init__()
        self._output = output

    def emit_record(self, record):
        self._output.append(record)
