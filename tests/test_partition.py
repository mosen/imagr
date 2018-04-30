import unittest
import os
import sys

sys.path.append(os.path.dirname(__file__) + '/../Imagr')
sys.path.append(os.path.dirname(__file__) + '/../Imagr/gmacpyutil')
from tasks import PartitionTask
from delegates import CLIProgressDelegate
from fixtures import TargetVolumeFixture


class TestPartitionTask(unittest.TestCase, TargetVolumeFixture):

    def setUp(self):
        self.make_target()

        self.item = {
            'type': 'partition',
            'map': 'GPTFormat',
            'partitions': [
                {
                    'format_type': 'Journaled HFS+',
                    'name': 'First',
                    'size': '50%',
                    'target': True
                },
                {
                    'format_type': 'Journaled HFS+',
                    'name': 'Second',
                    'size': '50%'
                }
            ]
        }

    def tearDown(self):
        if self.target:
            self.target.Unmount()

        if os.path.exists(self.output_temp):
            os.unlink(self.output_temp)

    def test_run(self):
        t = PartitionTask.alloc().initWithItem_target_(self.item, self.target)
        t.progressDelegate = CLIProgressDelegate.alloc().init()
        included_workflow = t.run()

        self.assertIsNone(included_workflow)
        self.assertTrue(os.path.exists("/Volumes/First"))
        self.assertTrue(os.path.exists("/Volumes/Second"))
        self.assertIsNotNone(t.newTarget())


if __name__ == '__main__':
    unittest.main()
