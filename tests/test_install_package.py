import unittest
import os
import sys

sys.path.append(os.path.dirname(__file__) + '/../Imagr')
sys.path.append(os.path.dirname(__file__) + '/../Imagr/gmacpyutil')
from tasks import InstallPackageTask
from delegates import CLIProgressDelegate
from fixtures import TargetVolumeFixture


class TestScriptTask(unittest.TestCase, TargetVolumeFixture):

    def setUp(self):
        self.make_target()
        self.serve_http()

        self.item = {
            'type': 'package',
            'url': self.url + "/munkitools-3.2.0.3476.pkg",
            'first_boot': False,
        }

        self.first_boot_item = {
            'type': 'package',
            'url': self.url + "/munkitools-3.2.0.3476.pkg",
        }

    def tearDown(self):
        if self.target:
            self.target.Unmount()

        if os.path.exists(self.output_temp):
            os.unlink(self.output_temp)

    def test_run(self):
        t = InstallPackageTask.alloc().initWithItem_target_(self.item, self.target)
        t.progressDelegate = CLIProgressDelegate.alloc().init()
        included_workflow = t.run()

        self.assertIsNone(included_workflow)

    # def test_firstboot_run(self):
    #     t = InstallPackageTask.alloc().initWithItem_target_(self.script_url, self.target)
    #     t.progressDelegate = CLIProgressDelegate.alloc().init()
    #     included_workflow = t.run()
    #
    #     self.assertIsNone(included_workflow)


if __name__ == '__main__':
    unittest.main()
