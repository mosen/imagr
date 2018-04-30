import unittest
import os
import sys

sys.path.append(os.path.dirname(__file__) + '/../Imagr')
sys.path.append(os.path.dirname(__file__) + '/../Imagr/gmacpyutil')
from tasks import ScriptTask
from delegates import CLIProgressDelegate
from fixtures import TargetVolumeFixture

EMBEDDED_SCRIPT = """#!/bin/bash
echo "ScriptWasRun"
"""


class TestScriptTask(unittest.TestCase, TargetVolumeFixture):

    def setUp(self):
        self.make_target()
        self.serve_http()

        self.script_embed = {
            'type': 'script',
            'content': EMBEDDED_SCRIPT,
            'first_boot': False,
        }

        self.script_url = {
            'type': 'script',
            'url': self.url + '/remote_script.sh',
        }

    def tearDown(self):
        if self.target:
            self.target.Unmount()

        if os.path.exists(self.output_temp):
            os.unlink(self.output_temp)

    def test_run(self):
        t = ScriptTask.alloc().initWithItem_target_(self.script_embed, self.target)
        t.progressDelegate = CLIProgressDelegate.alloc().init()
        included_workflow = t.run()

        self.assertIsNone(included_workflow)

    def test_run_url(self):
        t = ScriptTask.alloc().initWithItem_target_(self.script_url, self.target)
        t.progressDelegate = CLIProgressDelegate.alloc().init()
        included_workflow = t.run()

        self.assertIsNone(included_workflow)


if __name__ == '__main__':
    unittest.main()
