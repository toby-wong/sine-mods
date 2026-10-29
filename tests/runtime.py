"""Small loopback-only Marionette client used by Little Zen's runtime tests."""

import json
import socket


class Marionette:
    def __init__(self, port=2832):
        self.connection = socket.create_connection(("127.0.0.1", port), timeout=10)
        self.connection.settimeout(35)
        self.sequence = 0
        self.receive()
        self.command("WebDriver:NewSession", {"capabilities": {"alwaysMatch": {}}})
        self.command("Marionette:SetContext", {"value": "chrome"})
        self.command("WebDriver:SetTimeouts", {"script": 25000, "pageLoad": 25000})

    def receive(self):
        header = b""
        while not header.endswith(b":"):
            piece = self.connection.recv(1)
            if not piece:
                raise ConnectionError("Zen closed the automation connection")
            header += piece
        count = int(header[:-1])
        payload = bytearray()
        while count:
            piece = self.connection.recv(min(count, 1 << 20))
            if not piece:
                raise ConnectionError("Incomplete browser response")
            payload.extend(piece)
            count -= len(piece)
        return json.loads(payload)

    def command(self, name, params=None):
        self.sequence += 1
        payload = json.dumps([0, self.sequence, name, params or {}]).encode()
        self.connection.sendall(str(len(payload)).encode() + b":" + payload)
        reply = self.receive()
        if reply[:2] != [1, self.sequence]:
            raise RuntimeError(f"Unexpected browser response: {reply[:2]}")
        if reply[2]:
            raise RuntimeError(json.dumps(reply[2]))
        value = reply[3]
        return value.get("value", value) if isinstance(value, dict) else value

    def js(self, script, args=None):
        return self.command("WebDriver:ExecuteScript", {
            "script": script, "args": args or [], "newSandbox": True,
            "sandbox": "system", "filename": "little-zen-runtime-test", "line": 1,
        })

    def async_js(self, script, args=None):
        wrapped = """
          const complete = arguments[arguments.length - 1];
          (async () => { %s })().then(
            value => complete({ok:true, value}),
            error => complete({ok:false, error:String(error), stack:error.stack})
          );
        """ % script
        result = self.command("WebDriver:ExecuteAsyncScript", {
            "script": wrapped, "args": args or [], "newSandbox": True,
            "sandbox": "system", "filename": "little-zen-runtime-test", "line": 1,
        })
        if not result["ok"]:
            raise RuntimeError(result)
        return result.get("value")

    def close(self):
        try:
            self.connection.settimeout(3)
            self.command("WebDriver:DeleteSession")
        finally:
            self.connection.close()
