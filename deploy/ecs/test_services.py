import importlib.machinery
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
import subprocess

loader = importlib.machinery.SourceFileLoader('services', str(Path(__file__).with_name('olivetin-services')))
spec = importlib.util.spec_from_loader(loader.name, loader)
services = importlib.util.module_from_spec(spec)
loader.exec_module(services)


class ServiceBoundaryTests(unittest.TestCase):
    def test_latest_login_event_and_unknown(self):
        self.assertEqual(services.qq_login('nothing')['QQ 登录'], 'unknown')
        text = '2026-10-02T01:00:00Z 请扫描二维码\n2026-10-02T01:01:00Z 登录成功'
        self.assertEqual(services.qq_login(text)['QQ 登录'], 'logged-in')
        self.assertEqual(services.qq_login(text + '\n2026-10-02T01:02:00Z 被迫下线')['QQ 登录'], 'login-required')

    def test_actual_events_and_advisory_false_positive(self):
        advisory = '2026-10-04T07:00:00Z [WebUi] 新密码将在QQ登录成功后发送给用户'
        self.assertEqual(services.parse_login(advisory)['status'], 'unknown')
        qr = '2026-10-04T07:01:00Z 二维码已保存到 /app/napcat/cache/qrcode.png'
        info = services.parse_login(advisory + '\n' + qr)
        self.assertEqual(info['status'], 'login-required')
        self.assertTrue(info['qrEventAt'])
        for event, status in [('[Core] [Login] Login Error,ErrType: 1 ErrCode:3', 'expired'),
                              ('[Core] [Login] Login Error , ErrInfo: [redacted]', 'failed'),
                              ('[NapCat] 已通知主进程登录成功', 'logged-in'),
                              ('被迫下线', 'login-required')]:
            info = services.parse_login(qr + '\n2026-10-04T07:02:00Z ' + event)
            self.assertEqual(info['status'], status)
            self.assertFalse(info['qrEventAt'])
        self.assertEqual(services.parse_login(qr + '\n2026-10-04T07:03:00Z ' + qr.split(' ', 1)[1])['eventAt'], '2026-10-04T07:03:00Z')

    def test_qr_freshness_fixed_path_and_png(self):
        at = services.epoch('2026-10-04T07:01:00Z')
        def info():
            return services.parse_login('2026-10-04T07:01:00Z 二维码已保存到 /app/napcat/cache/qrcode.png')
        with patch.object(services, 'run', return_value=f'12 {int(at)}') as stat, \
                patch.object(services.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, b'\x89PNG\r\n\x1a\nDATA')) as image:
            result = services.attach_qr(info(), '2026-10-04T07:00:00Z', at + 10)
            self.assertTrue(result['qrImage'].startswith('data:image/png;base64,'))
            self.assertEqual(image.call_args.args[0][-1], services.QR_PATH)
            image.reset_mock()
            self.assertEqual(services.attach_qr(info(), '2026-10-04T07:00:00Z', at + 121)['status'], 'expired')
            image.assert_not_called()
            self.assertNotIn('qrImage', services.attach_qr(info(), '2026-10-04T07:02:00Z', at + 10))
            self.assertNotIn('qrImage', services.attach_qr(services.parse_login('2026-10-04T07:02:00Z 登录成功'), '2026-10-04T07:00:00Z', at + 10))
            image.return_value = subprocess.CompletedProcess([], 0, b'<html>oops</html>')
            self.assertNotIn('qrImage', services.attach_qr(info(), '2026-10-04T07:00:00Z', at + 10))
        with self.assertRaises(ValueError):
            services.main(['login', 'astrbot'])

    def test_secrets_and_terminal_codes_are_filtered(self):
        text = '\x1b[31mapi_key="test-secret" token=abc password: xyz Bearer some-secret https://user:pass@host/path?k=secret\x1b[0m'
        cleaned = services.sanitize(text)
        for forbidden in ['test-secret', 'abc', 'xyz', 'some-secret', 'user:pass', 'k=secret', '\x1b']:
            self.assertNotIn(forbidden, cleaned)

    def test_authorization_and_cookie_headers(self):
        for text in ['Authorization: Bearer test-secret', 'Authorization: Basic dXNlcjpzZWNyZXQ=', 'Cookie: session=test-secret; other=another-secret']:
            cleaned = services.sanitize(text)
            for value in ['test-secret', 'dXNlcjpzZWNyZXQ=', 'another-secret']:
                self.assertNotIn(value, cleaned)

    def test_fixed_service_operations(self):
        for args in [['restart', 'docker'], ['stop', 'wireguard'], ['logs', '../../etc/shadow'], ['exec', 'astrbot']]:
            with self.assertRaises(ValueError):
                services.main(args)

    def test_unicode_logs_fit_byte_limit(self):
        cleaned = services.sanitize('日志' * 100000)
        self.assertLessEqual(len(cleaned.encode('utf-8')), 160 * 1024)
        self.assertTrue(cleaned.endswith('日志'))


if __name__ == '__main__':
    unittest.main()
