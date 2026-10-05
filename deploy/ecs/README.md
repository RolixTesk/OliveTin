# Rolix ECS service management fork

This deployment builds `https://github.com/RolixTesk/OliveTin` with the service monitoring extension. Do not substitute an upstream image or release binary.

The `/system` page reads existing Alibaba CloudMonitor history through the existing `openapi-mcp-core` OAuth grant and root-only DNS client's transport. CPU, memory and filesystem utilization use line charts; system load and per-interface traffic are also shown. Only this ECS and fixed metrics are queried. No monitoring daemon, database, cloud identity or public endpoint is added. The authenticated `/service-monitor/system?range=1h` endpoint accepts only `1h`, `6h` and `24h` (60/300/900-second averages) and shares a one-minute cache per range. Missing samples remain gaps; failed collection preserves successful cache with a warning. OAuth credentials remain root-only; access-token expiry uses the existing refresh method. The existing CloudMonitor agent and authorized cloud grant are prerequisites.

The `/services` page samples the fixed collector every 10 seconds and displays runtime state, startup policy, container health, passive listener information, WireGuard handshake age and NapCat login events. Failed collection preserves the last timestamp and is marked stale. Business logs are fetched separately from action history, limited to 200 lines and 160 KiB, and filtered for common credential fields, bearer tokens and URL queries. Systemd journals cover this boot and the last 24 hours to avoid expensive scans of unrelated historical entries. Unknown QQ state is not reported as offline.

The backend extension is optional, configured by `serviceMonitor`. Its read-only endpoints `/service-monitor/status`, `/service-monitor/logs/{id}` and `/service-monitor/napcat-login` require an authenticated account with an explicitly allowed ACL. Service changes use OliveTin's existing executor, action ACLs, confirmations, action groups and logs. The root-owned helper permits only fixed service names and operations. Docker and WireGuard lifecycle changes remain SSH operations; Nginx allows a configuration check and validated reload.

## Build

```sh
cd frontend
npm ci
npm run build
cd ../service
go test ./...
go build -trimpath -o OliveTin .
```

The example configuration is JSON, which the YAML loader also accepts. Replace the example hash privately. Install the binary and frontend assets together in a versioned release directory, point `/opt/olivetin/current` at that directory, and set `webUIDir` to its `webui` subdirectory. Preserve the fork source and release manifest alongside the binary.

## Runtime files

| File | Purpose and ownership |
| --- | --- |
| `/etc/OliveTin/config.yaml` | root:olivetin, 0640; fixed actions and password hash |
| `/etc/OliveTin/sessions.yaml` | olivetin:olivetin, 0600; writable session persistence, config directory remains root-owned |
| `/etc/OliveTin/admin-credentials.json` | root:root, 0600; initial management login, never commit or print in logs |
| `/usr/local/libexec/olivetin-services` | root-owned fixed collector and operations |
| `/etc/sudoers.d/olivetin` | permits only that helper |
| `/etc/systemd/system/olivetin.service` | fork startup, non-root user, loopback HTTP |
| `/etc/systemd/system/astrbot.service` | existing rolix CLI/context, replaces tmux, SIGINT shutdown |
| `/etc/letsencrypt/olivetin-dns-credentials.json` | root:root, 0600; existing Alibaba OAuth credentials, never readable by OliveTin |
| `/usr/local/libexec/olivetin-dns` | fixed-domain Certbot DNS-01 hooks using `openapi-mcp-core` |

Obtain the initial account privately through SSH:

```sh
sudo cat /etc/OliveTin/admin-credentials.json
```

DNS A points at `10.66.0.1`, with no AAAA. Nginx checks destination `.1` and trusted source `.1/.2/.3`; INPUT additionally requires wg0 for remote clients. Server-local `.1` access is allowed through loopback. Rules apply only to `.1:443`, leave public addresses and Docker forwarding unchanged, and are persisted in existing WireGuard lifecycle hooks without restarting the tunnel.

Certbot uses its existing timer with the fixed-domain DNS auth/cleanup hooks. The hooks refresh the existing Alibaba OAuth grant, add only their validation TXT record, and remove only the verified record they created. They do not create IAM users, RAM roles, AccessKeys or new public listeners. Revoking or expiring this OAuth grant requires privately updating the certificate credential file; it is separate from the OliveTin account.

## Service-specific behavior

- AstrBot: systemd state and port listeners; stop does not disable future boot startup.
- NapCat: container health and latest recognized QQ login event from current-container logs; the styled login panel reads the fixed current QR PNG and reports event/check timestamps. Images have a conservative 120-second display window, are cleared on expiry or a subsequent login/logout/failure event, and are never persisted in action history.
- Clash: existing `clashon --service-only` and `clashoff --service-only` run as rolix; existing nohup implementation and log file are retained.
- CouchDB, Stalwart, Roundcube: named-container lifecycle and business logs; stopping with `unless-stopped` keeps the container stopped across reboot.
- HoyoPanel: existing unit lifecycle and journal.
- Nginx: HTTP access/error logs and configuration validation before reload.
- WireGuard: existing peer handshake information; no panel button that disconnects its own transport.

The personal-site theme is bundled locally and uses the existing light/dark preference. QQ login-event detection does not prove OneBot connectivity or successful message processing; actual account authorization is performed by the user on their phone.
