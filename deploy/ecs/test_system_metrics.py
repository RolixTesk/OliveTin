import importlib.util
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('system_metrics', Path(__file__).with_name('system_metrics.py'))
metrics = importlib.util.module_from_spec(spec)
spec.loader.exec_module(metrics)


class LocalMetricsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.proc = self.root / 'proc'
        (self.proc / 'net').mkdir(parents=True)
        (self.proc / 'sys/kernel/random').mkdir(parents=True)
        (self.proc / 'sys/kernel/random/boot_id').write_text('boot-one')
        (self.proc / 'meminfo').write_text('MemTotal: 1000 kB\nMemAvailable: 250 kB\n')
        (self.proc / 'loadavg').write_text('0.15 0.25 0.30 1/100 1000')
        (self.proc / 'mounts').write_text('/dev/vda3 / ext4 rw 0 0\n/dev/vda2 /boot/efi vfat rw 0 0\n/dev/loop0 /snap/test squashfs ro 0 0\n')
        self.counters(False)
        self.patches = [patch.object(metrics, 'PROC', self.proc),
                        patch.object(metrics, 'HISTORY_PATH', self.root / 'history.sqlite3'),
                        patch.object(metrics.os, 'statvfs', return_value=SimpleNamespace(f_blocks=1000, f_bfree=400, f_bavail=350))]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()

    def counters(self, second):
        cpu = '140 0 60 900 20 0 0 0 130 20' if second else '100 0 50 850 20 0 0 0 100 20'
        (self.proc / 'stat').write_text('cpu ' + cpu + '\ncpu0 0\n')
        rx, tx = (2250, 4500) if second else (1000, 2000)
        (self.proc / 'net/dev').write_text('Inter-| Receive | Transmit\n eth0: ' + str(rx) + ' 0 0 0 0 0 0 0 ' + str(tx) + ' 0 0 0 0 0 0 0\n wg0: 10 0 0 0 0 0 0 0 20 0 0 0 0 0 0 0\n lo: 1 0 0 0 0 0 0 0 1 0 0 0 0 0 0 0\n')

    def collect(self, stamp):
        with patch.object(metrics.time, 'time', return_value=stamp), patch.object(metrics.time, 'monotonic', return_value=stamp):
            metrics.collect()

    def history(self, stamp, window='1h'):
        with patch.object(metrics.time, 'time', return_value=stamp):
            return metrics.history(window)

    def test_native_counters_and_real_capacity(self):
        self.collect(1000000)
        self.counters(True)
        self.collect(1000010)
        result = self.history(1000010)
        data = result['metrics']
        self.assertEqual(result['source'], 'Linux OS')
        self.assertEqual(data['cpu']['series'][0]['points'][0][1], 50)
        self.assertEqual(data['memory']['series'][0]['points'][0][1], 75)
        self.assertAlmostEqual(data['disk']['series'][0]['points'][0][1], 600 / 950 * 100)
        self.assertEqual(data['networkIn']['series'][0]['points'][0][1], 1000)
        self.assertEqual(data['networkOut']['series'][0]['points'][0][1], 2000)
        self.assertEqual(len(data['disk']['series']), 2)
        self.assertEqual(len(data['networkIn']['series']), 2)
        self.assertEqual(metrics.HISTORY_PATH.stat().st_mode & 0o777, 0o600)

    def test_first_sample_is_not_a_fake_zero(self):
        self.collect(1000000)
        result = self.history(1000000)
        self.assertEqual(result['metrics']['cpu']['series'], [])
        self.assertEqual(result['metrics']['networkIn']['series'], [])
        self.assertTrue(result['metrics']['memory']['series'])
        self.assertEqual(result['historyStart'], 1000000000)

    def test_aggregation_preserves_real_time_and_average(self):
        self.collect(1000000)
        (self.proc / 'meminfo').write_text('MemTotal: 1000 kB\nMemAvailable: 500 kB\n')
        self.collect(1000010)
        result = self.history(1000010)
        self.assertEqual(result['metrics']['memory']['series'][0]['points'], [[1000010000, 62.5]])

    def test_partial_failure_keeps_other_metrics(self):
        (self.proc / 'meminfo').write_text('MemTotal: broken\n')
        self.collect(1000000)
        result = self.history(1000000)
        self.assertTrue(result['metrics']['memory']['error'])
        self.assertTrue(result['metrics']['disk']['series'])
        self.assertTrue(result['metrics']['load1']['series'])

    def test_rates_do_not_cross_reboot_or_counter_reset(self):
        self.collect(1000000)
        self.counters(True)
        (self.proc / 'sys/kernel/random/boot_id').write_text('boot-two')
        self.collect(1000010)
        self.assertEqual(self.history(1000010)['metrics']['cpu']['series'], [])
        self.counters(False)
        self.collect(1000020)
        self.assertEqual(self.history(1000020)['metrics']['cpu']['series'], [])
        devices = [item['device'] for item in self.history(1000020)['metrics']['networkIn']['series']]
        self.assertNotIn('eth0', devices)

    def test_history_survives_reopen_and_expires(self):
        self.collect(1000000)
        self.counters(True)
        self.collect(1000010)
        self.assertTrue(self.history(1000010, '24h')['metrics']['cpu']['series'])
        self.assertTrue(self.history(1000010, '6h')['metrics']['cpu']['series'])
        self.collect(1086420)
        result = self.history(1086420, '24h')
        self.assertEqual(result['metrics']['cpu']['series'], [])
        self.assertEqual(result['historyStart'], 1086420000)
        self.assertEqual(result['metrics']['memory']['series'][0]['points'], [[1086420000, 75]])

    def test_history_request_does_not_sample_or_use_network(self):
        self.collect(1000000)
        with patch.object(metrics, 'capture', side_effect=AssertionError('read request must not sample')):
            result = self.history(1000031)
        self.assertEqual(result['sampledAt'], 1000000000)
        self.assertEqual(result['warning'], 'sampling-delayed')
        with self.assertRaises(ValueError):
            self.history(1000031, '7d')


if __name__ == '__main__':
    unittest.main()
