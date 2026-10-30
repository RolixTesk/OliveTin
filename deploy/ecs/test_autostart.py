import importlib.machinery
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

loader = importlib.machinery.SourceFileLoader('services', str(Path(__file__).with_name('olivetin-services')))
spec = importlib.util.spec_from_loader(loader.name, loader)
services = importlib.util.module_from_spec(spec)
loader.exec_module(services)


class AutostartTests(unittest.TestCase):
    def test_compose_edit_only_changes_selected_service_and_preserves_comments(self):
        text = 'services:\n  one:\n    restart: "no" # keep\n    image: test\n  two:\n    restart: always\nnetworks:\n  one:\n    driver: bridge\n'
        actual = services.replace_restart(text, 'one', 'always')
        self.assertEqual(actual, text.replace('restart: "no" # keep', 'restart: "always" # keep'))
        for bad in ['services:\n  one:\n    image: test\n', text.replace('    image: test', '    restart: no'), text.replace('  two:', '  one:')]:
            with self.assertRaises(services.AutostartError):
                services.replace_restart(bad, 'one', 'no')

    def test_unit_policy_changes_do_not_restart_running_service(self):
        for verb, old, wanted, command in [('enable-autostart', 'disabled', 'enabled', 'enable'), ('disable-autostart', 'enabled', 'disabled', 'disable')]:
            with patch.object(services, 'unit_info', side_effect=[{'enabled': old}, {'enabled': wanted}]), patch.object(services, 'run', return_value='') as run:
                services.mutate(verb, 'astrbot')
            self.assertEqual(run.call_args.args[0], ['/usr/bin/systemctl', command, 'astrbot.service'])

    def test_unsupported_unit_state_and_infrastructure_are_rejected(self):
        with patch.object(services, 'unit_info', return_value={'enabled': 'static'}), patch.object(services, 'run') as run:
            with self.assertRaises(services.AutostartError): services.mutate('enable-autostart', 'astrbot')
            run.assert_not_called()
        for name in ['docker', 'wireguard', 'nginx', '../../etc/shadow']:
            with self.assertRaises(ValueError): services.mutate('enable-autostart', name)

    def test_unit_failure_rolls_back_previous_policy(self):
        with patch.object(services, 'unit_info', return_value={'enabled': 'enabled'}), patch.object(services, 'run', side_effect=[RuntimeError('failed'), '']) as run:
            with self.assertRaisesRegex(services.AutostartError, '已恢复'): services.mutate('disable-autostart', 'astrbot')
            self.assertEqual(run.call_args.args[0][1], 'enable')

    def test_docker_policy_and_compose_commit_or_rollback(self):
        for verb, original, target, state, fail in [
            ('enable-autostart', 'no', 'always', 'exited', False),
            ('disable-autostart', 'always', 'no', 'running', False),
            ('disable-autostart', 'unless-stopped', 'no', 'running', True),
        ]:
            with self.subTest(verb=verb, fail=fail), tempfile.TemporaryDirectory() as td:
                p = Path(td) / 'compose.yml'; text = f'services:\n  box:\n    restart: "{original}"\n'; p.write_text(text)
                state_data = {'restart': original, 'state': state, 'started': 'unchanged'}
                commands = []
                def run(args, **kwargs):
                    commands.append(args)
                    if args[1] == 'compose':
                        file = Path(args[args.index('-f') + 1]); value = 'always' if '"always"' in file.read_text() else 'unless-stopped' if '"unless-stopped"' in file.read_text() else 'no'
                        return json.dumps({'services': {'box': {'restart': value, 'image': 'same'}}})
                    if args[1] == 'update':
                        value = args[2].split('=', 1)[1]
                        if fail and value == target: raise RuntimeError('failed')
                        state_data['restart'] = value
                        return ''
                    raise AssertionError(args)
                with patch.object(services, 'COMPOSE_SERVICES', {'stalwart': (str(p), 'box')}), patch.object(services, 'AUTOSTART_BACKUPS', Path(td) / 'backups'), patch.object(services, 'container_info', side_effect=lambda _: dict(state_data)), patch.object(services, 'run', side_effect=run):
                    if fail:
                        with self.assertRaisesRegex(services.AutostartError, '已恢复'): services.mutate(verb, 'stalwart')
                        self.assertEqual(p.read_text(), text); self.assertEqual(state_data['restart'], original)
                    else:
                        services.mutate(verb, 'stalwart')
                        self.assertIn(f'restart: "{target}"', p.read_text()); self.assertEqual(state_data['restart'], target)
                    self.assertEqual(state_data['state'], state)
                    self.assertTrue(all('start' not in a and 'stop' not in a and 'restart' not in a for a in commands))

    def test_inconsistent_compose_refuses_mutation(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'compose.yml';p.write_text('services:\n  box:\n    restart: "no"\n')
            with patch.object(services, 'COMPOSE_SERVICES', {'stalwart': (str(p),'box')}), patch.object(services, 'container_info', return_value={'restart':'always'}), patch.object(services, 'run') as run:
                with self.assertRaises(services.AutostartError):services.mutate('enable-autostart','stalwart')
                run.assert_not_called()

    def test_unrelated_compose_changes_fail_validation(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'compose.yml';p.write_text('services:\n  box:\n    restart: "no"\n')
            docs=[{'services':{'box':{'restart':'no','image':'one'}}}, {'services':{'box':{'restart':'always','image':'other'}}}]
            with patch.object(services,'COMPOSE_SERVICES',{'stalwart':(str(p),'box')}),patch.object(services,'AUTOSTART_BACKUPS',Path(td)/'backups'),patch.object(services,'container_info',return_value={'restart':'no'}),patch.object(services,'run',side_effect=[json.dumps(x) for x in docs]):
                with self.assertRaises(services.AutostartError):services.mutate('enable-autostart','stalwart')
                self.assertIn('restart: "no"',p.read_text())


if __name__ == '__main__': unittest.main()
