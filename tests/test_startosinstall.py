import unittest
import os
import sys

sys.path.append(os.path.dirname(__file__) + '/../Imagr')
sys.path.append(os.path.dirname(__file__) + '/../Imagr/gmacpyutil')
from tasks import StartOSInstallTask
from delegates import CLIProgressDelegate
from fixtures import TargetVolumeFixture


class TestStartOSInstallTask(unittest.TestCase, TargetVolumeFixture):

    def setUp(self):
        self.make_target()
        self.serve_http()

        self.item = {
            'type': 'startosinstall',
            'url': self.url + '/Install%20macOS%20High%20Sierra-10.13.dmg',
        }

        self.ramdisk_item = {
            'type': 'startosinstall',
            'url': self.url + '/Install%20macOS%20High%20Sierra-10.13.dmg',
            'ramdisk': True,
        }

    def tearDown(self):
        if self.target:
            self.target.Unmount()

        os.unlink(self.output_temp)

    def test_run_dry(self):
        t = StartOSInstallTask.alloc().initWithItem_target_(self.item, self.target)
        t.progressDelegate = CLIProgressDelegate.alloc().init()
        included_workflow = t.run(dry=True)
        self.assertIsNone(included_workflow)



if __name__ == '__main__':
    unittest.main()
