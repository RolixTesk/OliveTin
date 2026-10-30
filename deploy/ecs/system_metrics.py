"""Local Linux samples and bounded history, run as the existing olivetin user."""
from contextlib import closing
import json
import os
from pathlib import Path
import re
import sqlite3
import time

PROC = Path('/proc')
HISTORY_PATH = Path('/var/lib/olivetin/system-monitor.sqlite3')
INTERVAL = 10
RANGES = {'1h': (3600, 60), '6h': (21600, 300), '24h': (86400, 900)}
METRICS = {
    'cpu': ('cpu_total', '%', 'cpu'), 'memory': ('memory_usedutilization', '%', 'memory'),
    'disk': ('diskusage_utilization', '%', 'disk'), 'load1': ('load_1m', '', 'load'),
    'load5': ('load_5m', '', 'load'), 'networkIn': ('networkin_rate', 'bit/s', 'network'),
    'networkOut': ('networkout_rate', 'bit/s', 'network'),
}


def cpu_counters():
    values = [int(value) for value in (PROC / 'stat').read_text().splitlines()[0].split()[1:9]]
    return [sum(values), values[3]]  # Guest time is already included in user/nice counters.


def memory_usage():
    fields = {line.split(':')[0]: int(line.split()[1]) for line in (PROC / 'meminfo').read_text().splitlines()}
    total = fields['MemTotal']
    available = fields.get('MemAvailable')
    if available is None:
        available = sum(fields.get(name, 0) for name in ['MemFree', 'Buffers', 'Cached', 'SReclaimable']) - fields.get('Shmem', 0)
    if total <= 0 or not 0 <= available <= total:
        raise ValueError('Invalid memory counters')
    return 100 * (total - available) / total


def network_counters():
    result = {}
    for line in (PROC / 'net/dev').read_text().splitlines():
        if ':' not in line:
            continue
        name, values = line.split(':', 1)
        name = name.strip()
        if name == 'lo' or name.startswith('veth'):
            continue
        fields = values.split()
        result[name] = [int(fields[0]), int(fields[8])]
    return result


def disk_usage():
    result = {}
    for line in (PROC / 'mounts').read_text().splitlines():
        device, mount = line.split()[:2]
        if not device.startswith('/dev/') or device.startswith('/dev/loop') or device in result:
            continue
        mount = re.sub(r'\\([0-7]{3})', lambda match: chr(int(match[1], 8)), mount)
        try:
            stat = os.statvfs(mount)
            used = stat.f_blocks - stat.f_bfree
            value = 100 * used / (used + stat.f_bavail)
            result[device] = (device, mount, value)
        except (OSError, ZeroDivisionError):
            continue
    if not result:
        raise OSError('No readable disk filesystems')
    return list(result.values())


def capture():
    result = {'time': int(time.time() * 1000), 'monotonic': time.monotonic(),
              'boot': (PROC / 'sys/kernel/random/boot_id').read_text().strip(), 'errors': {}}
    sources = {'cpu': cpu_counters, 'memory': memory_usage, 'disk': disk_usage,
               'network': network_counters, 'load': lambda: [float(x) for x in (PROC / 'loadavg').read_text().split()[:2]]}
    for name, source in sources.items():
        try:
            result[name] = source()
        except (OSError, ValueError, IndexError, KeyError):
            result[name] = None
            result['errors'][name] = 'OS metric unavailable'
    return result


def rate_values(current, previous):
    if not previous or previous['boot'] != current['boot']:
        return []
    elapsed = current['monotonic'] - previous['monotonic']
    if not 0 < elapsed <= INTERVAL * 3:
        return []
    result = []
    if current['cpu'] and previous['cpu']:
        total, idle = (current['cpu'][i] - previous['cpu'][i] for i in range(2))
        if total > 0 and 0 <= idle <= total:
            result.append(('cpu', '', '', 100 * (total - idle) / total))
    for device, counters in (current['network'] or {}).items():
        before = (previous['network'] or {}).get(device)
        if before and all(counters[i] >= before[i] for i in range(2)):
            result.extend((key, device, device, (counters[i] - before[i]) * 8 / elapsed)
                          for i, key in enumerate(['networkIn', 'networkOut']))
    return result


def sample_values(current, previous):
    result = rate_values(current, previous)
    if current['memory'] is not None:
        result.append(('memory', '', '', current['memory']))
    if current['load'] is not None:
        result.extend((key, '', '', current['load'][i]) for i, key in enumerate(['load1', 'load5']))
    result.extend(('disk', device, mount, value) for device, mount, value in (current['disk'] or []))
    return result


def connect_history():
    HISTORY_PATH.touch(mode=0o600, exist_ok=True)
    db = sqlite3.connect(HISTORY_PATH, timeout=2)
    db.executescript('''
        CREATE TABLE IF NOT EXISTS samples (
            stamp INTEGER NOT NULL, metric TEXT NOT NULL, device TEXT NOT NULL,
            name TEXT NOT NULL, value REAL NOT NULL, PRIMARY KEY (stamp, metric, device));
        CREATE TABLE IF NOT EXISTS state (id INTEGER PRIMARY KEY CHECK (id=1), data TEXT NOT NULL);
    ''')
    return db


def collect():
    current = capture()
    with closing(connect_history()) as db, db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT data FROM state WHERE id=1').fetchone()
        previous = json.loads(row[0]) if row else None
        if previous and 0 <= current['time'] - previous['time'] < (INTERVAL - 1) * 1000:
            return {'sampledAt': previous['time']}
        values = sample_values(current, previous)
        db.executemany('INSERT OR REPLACE INTO samples VALUES (?,?,?,?,?)',
                       [(current['time'], *value) for value in values])
        db.execute('INSERT OR REPLACE INTO state VALUES (1,?)', (json.dumps(current),))
        db.execute('DELETE FROM samples WHERE stamp < ?', (current['time'] - 86400000,))
    return {'sampledAt': current['time']}


def history(window):
    if window not in RANGES:
        raise ValueError('Unknown monitoring range')
    seconds, period = RANGES[window]
    end = int(time.time() * 1000)
    start = end - seconds * 1000
    with closing(connect_history()) as db:
        rows = db.execute('''SELECT metric,device,name,MAX(stamp),AVG(value) FROM samples
            WHERE stamp > ? AND stamp <= ? GROUP BY metric,device,name,CAST(stamp / ? AS INTEGER)
            ORDER BY metric,device,MAX(stamp)''', (start, end, period * 1000)).fetchall()
        first, last = db.execute('SELECT MIN(stamp),MAX(stamp) FROM samples WHERE stamp <= ?', (end,)).fetchone()
        row = db.execute('SELECT data FROM state WHERE id=1').fetchone()
    errors = json.loads(row[0]).get('errors', {}) if row else {}
    groups = {key: {} for key in METRICS}
    for key, device, name, stamp, value in rows:
        group = groups[key].setdefault(device, {'device': device, 'name': name or device, 'points': []})
        group['points'].append([stamp, value])
    metrics = {key: {'metric': metric, 'unit': unit, 'series': list(groups[key].values()),
                     **({'error': 'OS metric unavailable'} if sensor in errors else {})}
               for key, (metric, unit, sensor) in METRICS.items()}
    warning = 'warming-up' if not metrics['cpu']['series'] else ''
    if last and end - last > INTERVAL * 3000:
        warning = 'sampling-delayed'
    return {'source': 'Linux OS', 'range': window, 'period': period, 'sampleInterval': INTERVAL,
            'startTime': start, 'endTime': end, 'historyStart': first, 'sampledAt': last,
            'warning': warning, 'metrics': metrics}
