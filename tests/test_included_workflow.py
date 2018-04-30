import unittest
import os
import sys
import subprocess
import re
import tempfile
import shutil

sys.path.append(os.path.dirname(__file__) + '/../Imagr')
sys.path.append(os.path.dirname(__file__) + '/../Imagr/gmacpyutil')
from tasks import IncludedWorkflowTask
import macdisk

SCRIPTED_INCLUSION = """#!/bin/bash
echo "ImagrIncludedWorkflow: test_included_script"
"""

PLACEHOLDER_INCLUSION = """#!/bin/bash
echo "ImagrIncludedWorkflow: {{language}}"
"""


class TestIncludedWorkflowTask(unittest.TestCase):
    def setUp(self):
        self.item = {
            'type': 'included_workflow',
            'name': 'test_included',
        }

        self.scripted_item = {
            'type': 'included_workflow',
            'script': SCRIPTED_INCLUSION,
        }

        self.placeholder_item = {
            'type': 'included_workflow',
            'script': PLACEHOLDER_INCLUSION,
        }

    def tearDown(self):
        pass
        # self.target.Unmount()
        # os.unlink(self.output_temp)

    def test_run_static(self):
        t = IncludedWorkflowTask.alloc().initWithItem_target_(self.item, self.target)
        included_workflow = t.run(dry=True)
        self.assertIsNotNone(included_workflow)
        print(included_workflow)

    def test_run_script(self):
        t = IncludedWorkflowTask.alloc().initWithItem_target_(self.scripted_item, self.target)
        included_workflow = t.run(dry=True)
        self.assertIsNotNone(included_workflow)
        print(included_workflow)

    def test_run_placeholder_script(self):
        t = IncludedWorkflowTask.alloc().initWithItem_target_(self.placeholder_item, self.target)
        included_workflow = t.run(dry=True)
        self.assertIsNotNone(included_workflow)
        print(included_workflow)


if __name__ == '__main__':
    unittest.main()
