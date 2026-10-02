import importlib.machinery
import importlib.util
from pathlib import Path
import unittest

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
