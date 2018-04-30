import unittest
import os
import sys

sys.path.append(os.path.dirname(__file__) + '/../Imagr')
sys.path.append(os.path.dirname(__file__) + '/../Imagr/gmacpyutil')
from tasks import ImageTask
from delegates import CLIProgressDelegate
from fixtures import TargetVolumeFixture


class TestImageTask(unittest.TestCase, TargetVolumeFixture):

    def setUp(self):
        self.make_target()
        self.serve_http()

        self.item = {
            'type': 'image',
            'url': self.url + '/test.dmg',
        }

        self.ramdisk_item = {
            'type': 'image',
            'url': self.url + '/test.dmg',
            'ramdisk': True,
        }

    def tearDown(self):
        if self.target:
            self.target.Unmount()

        if os.path.exists(self.output_temp):
            os.unlink(self.output_temp)

    def test_run(self):
        t = ImageTask.alloc().initWithItem_target_(self.item, self.target)
        t.progressDelegate = CLIProgressDelegate.alloc().init()
        included_workflow = t.run(dry=False)

        self.assertIsNone(included_workflow)




if __name__ == '__main__':
    unittest.main()
