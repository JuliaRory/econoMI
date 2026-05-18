class CallDispatcher:
    def __init__(self):
        self.reset()

    def reset(self):
        self._call = self._none

    def set_callback(self, callback):
        self._call = callback

    def _none(self, *args, **kwargs):
        return None

    def __call__(self, *args, **kwargs):
        return self._call(*args, **kwargs)
