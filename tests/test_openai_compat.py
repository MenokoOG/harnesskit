import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from harnesskit.loop import Agent
from harnesskit.openai_compat import OpenAICompatModel, parse_args
from harnesskit.tools import default_tools


def message(content="", calls=()):
    return {"choices": [{"message": {"content": content, "tool_calls": [
        {"id": f"w{i}", "type": "function", "function": {"name": n, "arguments": a}}
        for i, (n, a) in enumerate(calls)]}}]}


class FakeServer(BaseHTTPRequestHandler):
    script: list = []
    requests: list = []

    def do_POST(self):
        self.requests.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
        body = json.dumps(self.script.pop(0)).encode()
        self.send_response(200)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class AdapterTests(unittest.TestCase):
    def test_round_trip_through_the_loop(self):
        FakeServer.script = [message(calls=[("bash", '{"cmd": "echo hi"}')]), message("done")]
        FakeServer.requests = []
        server = HTTPServer(("127.0.0.1", 0), FakeServer)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        model = OpenAICompatModel(f"http://127.0.0.1:{server.server_port}", timeout=5)
        self.assertEqual(Agent(model, default_tools()).run("say hi"), "done")
        first, second = FakeServer.requests
        self.assertIn("cmd", first["tools"][0]["function"]["parameters"]["properties"])
        self.assertEqual(second["messages"][-1]["tool_call_id"], "w0")
        self.assertEqual(json.loads(second["messages"][-2]["tool_calls"][0]["function"]["arguments"]),
                         {"cmd": "echo hi"})

    def test_bad_json_arguments_survive_parsing(self):
        for raw in ("{oops", "[1]"):
            self.assertEqual(parse_args(raw), {"invalid_json_arguments": raw})


if __name__ == "__main__":
    unittest.main()
