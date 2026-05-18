import json


class ServiceProxy:
    def __init__(self, name, stream):
        self.name = name
        self._stream = stream

    def sendTransition(self, command, stream=None, add_stimuli=None, filename=None, app_service_name=None):
        message = {
            "service": self.name,
            "type": "command",
            "command": command,
            "stream": stream,
            "filename": filename,
            "app_service_name": app_service_name,
        }
        if add_stimuli is not None:
            message["add_stimuli"] = add_stimuli
        self._stream(json.dumps(message, ensure_ascii=False))
        print(f"[Proxy] Sent to {self.name}: {command}")

    def checkState(self):
        self._stream(json.dumps({"service": self.name, "type": "check"}, ensure_ascii=False))


class ResonanceAppProxy:
    def __init__(self, qml_stream):
        self._stream = qml_stream
        self._services = {}

    def getService(self, name):
        if name not in self._services:
            self._services[name] = ServiceProxy(name, self._stream)
        return self._services[name]
