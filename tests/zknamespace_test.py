"""Unit test for zknamespace.
"""

import unittest

from treadmill import zknamespace as z


class ZknamespaceTest(unittest.TestCase):
    """Mock test for treadmill.zknamespace."""

    def test_join_zookeeper_path(self):
        """Checks zookeeper path construction."""

        path = z.join_zookeeper_path('/root', 'node')
        self.assertEqual('/root/node', path)

        path = z.join_zookeeper_path('/root', 'node1', 'node2')
        self.assertEqual('/root/node1/node2', path)


if __name__ == "__main__":
    unittest.main()
