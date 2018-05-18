import unittest
import os
import sys

sys.path.append(os.path.dirname(__file__) + '/../Imagr/Resources')
sys.path.append(os.path.dirname(__file__) + '/../Imagr/gmacpyutil')

from fixtures import TargetVolumeFixture
from Utils import copyFirstBoot
import macdisk


class TestUtils(unittest.TestCase, TargetVolumeFixture):

    def setUp(self):
        self.target = None  # type: Optional[macdisk.Disk]
        self.make_target()

    def tearDown(self):
        if self.target:
            self.target.Unmount()

    def test_copyFirstBoot(self):
        copyFirstBoot(self.target.mountpoint)
        print(self.target)

if __name__ == '__main__':
    unittest.main()
