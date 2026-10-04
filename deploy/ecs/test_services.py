import importlib.machinery
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
import subprocess
import io
import json

loader = importlib.machinery.SourceFileLoader('services', str(Path(__file__).with_name('olivetin-services')))
spec = importlib.util.spec_from_loader(loader.name, loader)
services = importlib.util.module_from_spec(spec)
loader.exec_module(services)


class ServiceBoundaryTests(unittest.TestCase):
    def test_structured_messages_and_post_login_initialization(self):
        prefix = '2026-10-04T07:00:00.123456789Z 10-04 07:00:00 [info] '
        for body in ['[AdapterManager] OneBot11 适配器初始化完成',
                     '[AdapterManager] 协议适配器初始化完成，已加载 test',
                     '接收 <- 群聊 [test] [test] 登录失败 被迫下线',
                     '发送 -> 私聊 (test) [NapCat] [WebUi] WebUi Token: quoted']:
            self.assertEqual(services.parse_login(prefix + body)['status'], 'logged-in')
            self.assertIsNone(services.webui_token(prefix + body))
        text = prefix + '接收 <- 群聊 [test] [test] hi'
        offline = '2026-10-04T07:01:00Z [KickedOffLine] [test] disconnected'
        self.assertEqual(services.parse_login(offline + '\n' + text)['status'], 'login-required')

    def test_backward_batches_find_older_login_and_webui_information(self):
        start = '2026-10-04T07:00:00Z'
        event = start + ' [NapCat] 已通知主进程登录成功'
        token = start + ' [NapCat] [WebUi] WebUi Token: synthetic-token'
        filler = [f'2026-10-04T07:{1 + i // 60:02}:{i % 60:02}.000000000Z [Core] heartbeat' for i in range(600)]
        for target, first in [('login', event), ('token', token)]:
            calls = []
            def read_page(args, **kwargs):
                calls.append(args)
                tail = int(args[args.index('--tail') + 1])
                return '\n'.join(([first] + filler)[-tail:])
            with patch.object(services, 'run', side_effect=read_page):
                result = services.scan_napcat(start, target)
            self.assertEqual(result['scannedLines'], 601)
            self.assertEqual(len(calls), 4)
            self.assertEqual([int(args[args.index('--tail') + 1]) for args in calls], [200, 400, 600, 800])
            self.assertTrue(all(args[args.index('--since') + 1] == start for args in calls))
            self.assertTrue(all('--until' not in args for args in calls))
            if target == 'login':
                self.assertEqual(result['status'], 'logged-in')
            else:
                self.assertEqual(result['token'], 'synthetic-token')
                self.assertNotIn('synthetic-token', services.sanitize(first))

    def test_recent_message_stops_search_and_scan_keeps_newer_state(self):
        message = '2026-10-04T07:02:00Z 接收 <- 群聊 [test] [test] hi'
        with patch.object(services, 'napcat_log_pages', return_value=iter([message, 'old events'])):
            self.assertEqual(services.scan_napcat('2026-10-04T07:00:00Z')['scannedLines'], 1)
        scan = '2026-10-04T07:02:00Z onQRCodeSessionUserScaned'
        qr = '2026-10-04T07:01:00Z 二维码已保存到 /app/napcat/cache/qrcode.png'
        with patch.object(services, 'napcat_log_pages', return_value=iter([scan, qr])):
            result = services.scan_napcat('2026-10-04T07:00:00Z')
        self.assertEqual(result['status'], 'scanning')
        self.assertEqual(result['eventAt'], scan.split()[0])
        self.assertEqual(result['qrEventAt'], qr.split()[0])
        with patch.object(services, 'run', return_value='2026-10-04T07:00:00Z [Core] startup'):
            self.assertEqual(services.scan_napcat('2026-10-04T07:00:00Z')['status'], 'unknown')
        with patch.object(services, 'run', side_effect=subprocess.TimeoutExpired('docker', 1)):
            self.assertEqual(services.scan_napcat('2026-10-04T07:00:00Z')['status'], 'unknown')

    def test_stopped_token_does_not_read_old_history(self):
        output = io.StringIO()
        with patch.object(services, 'container_info', return_value={'state': 'exited', 'started': '2026-10-04T07:00:00Z'}), \
                patch.object(services, 'scan_napcat') as scan, patch('sys.stdout', output):
            services.token_info()
        scan.assert_not_called()
        self.assertEqual(json.loads(output.getvalue())['token'], '')

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
            self.assertAlmostEqual(services.epoch('2026-10-04T07:01:00.123456789Z'), at + .123456, places=5)
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
        for args in [['restart', 'docker'], ['stop', 'wireguard'], ['logs', '../../etc/shadow'], ['exec', 'astrbot'], ['token', 'astrbot']]:
            with self.assertRaises(ValueError):
                services.main(args)

    def test_unicode_logs_fit_byte_limit(self):
        cleaned = services.sanitize('日志' * 100000)
        self.assertLessEqual(len(cleaned.encode('utf-8')), 160 * 1024)
        self.assertTrue(cleaned.endswith('日志'))


if __name__ == '__main__':
    unittest.main()
