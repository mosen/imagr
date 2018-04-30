import unittest
import sys
import os

sys.path.append(os.path.dirname(__file__) + '/../Imagr')
sys.path.append(os.path.dirname(__file__) + '/../Imagr/gmacpyutil')
import Utils


class TestRamDisk(unittest.TestCase):

    def test_ramdisk(self):
        disk_dev, label = Utils.create_ramdisk(1000000)
        self.assertIsNotNone(disk_dev)
        self.assertIsNotNone(label)

        print disk_dev, label


if __name__ == '__main__':
    unittest.main()
