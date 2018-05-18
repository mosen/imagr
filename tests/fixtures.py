import subprocess
import tempfile
import re
import sys
import os
import SocketServer
import SimpleHTTPServer
import threading


sys.path.append(os.path.dirname(__file__) + '/../Imagr/gmacpyutil')
import macdisk

HTTP_PORT = 8001


class TestServer(SocketServer.TCPServer):
    allow_reuse_address = True


class TargetVolumeFixture(object):
    """TargetVolumeFixture creates a DMG which will be the target of disk operations on the machine running the Imagr test suite.
    It is still recommended to test in a VM.

    The type of the target property is macdisk.Disk
    """

    def make_target(self, size_spec="50M", label=__name__):
        self.output_temp = tempfile.mktemp(prefix="imagr", suffix="dmg")

        output = subprocess.check_output(["/usr/bin/hdiutil", "create", "-size", size_spec, "-volname",
                                          label, "-fs", "HFS+J", "-attach", self.output_temp])

        for line in output.split('\n'):
            print(line)
            match = re.search("^\/dev\/(disk[0-9]+[s][0-9])", line)
            if match:
                print(match)
                self.target = macdisk.Disk(match.group(1))

    def serve_http(self):
        """serve a temporary http web service intended to replicate a remote imagr source"""
        self.handler = SimpleHTTPServer.SimpleHTTPRequestHandler
        self.httpd = TestServer(("", HTTP_PORT), self.handler)

        self.httpd_thread = threading.Thread(target=self.httpd.serve_forever)
        self.httpd_thread.setDaemon(True)
        self.httpd_thread.start()
        self.url = "http://localhost:{}".format(HTTP_PORT)

    def teardown_http(self):
        pass
