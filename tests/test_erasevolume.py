import unittest
import os
import sys

sys.path.append(os.path.dirname(__file__) + '/../Imagr')
sys.path.append(os.path.dirname(__file__) + '/../Imagr/gmacpyutil')
from tasks import EraseVolumeTask
from delegates import CLIProgressDelegate
from fixtures import TargetVolumeFixture


class TestEraseVolumeTask(unittest.TestCase, TargetVolumeFixture):

    def setUp(self):
        self.make_target()

        self.item = {
            'type': 'eraseVolume',
            'name': 'My Volume Name',
            'format': 'Journaled HFS+'
        }

    def tearDown(self):
        if self.target:
            self.target.Unmount()

        if os.path.exists(self.output_temp):
            os.unlink(self.output_temp)

    def test_run(self):
        t = EraseVolumeTask.alloc().initWithItem_target_(self.item, self.target)
        t.progressDelegate = CLIProgressDelegate.alloc().init()
        included_workflow = t.run(dry=False)

        self.assertIsNone(included_workflow)
        self.assertTrue(os.path.exists("/Volumes/%s" % self.item['name']))



if __name__ == '__main__':
    unittest.main()
