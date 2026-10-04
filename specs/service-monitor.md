# Service monitoring

Service monitoring is optional and disabled unless explicitly enabled by the administrator. It samples the configured, administrator-controlled collector periodically, independently of browser visits. A failed sample preserves the last successful data and timestamp and visibly marks it as stale. Collection has time and output limits.

Only authenticated users belonging to an explicitly allowed access list can read snapshots or business logs. Guest users and authenticated users without this permission cannot access these endpoints. All monitoring endpoints are read-only and responses must not be cached.

Business log targets come from an explicit configured list. Unknown targets and path traversal attempts are rejected before collection. Business logs are bounded and sensitive data is filtered at the collector. They are separate from action execution records.

The service page displays runtime state, boot policy, health, collection time and service-specific details. A running container must not imply successful application login. Unknown or stale business state must be presented as unknown or stale.

After a successful login, an authenticated user can navigate to the service page and reload it without being redirected to login. Guests and unavailable session identities must still be redirected to login. Navigation uses the current server-provided identity, including after login or logout.

Service mutation buttons use the existing authorized action execution mechanism, including confirmations, concurrency limits and execution records. Monitoring does not expose arbitrary command execution, configuration editing or data deletion.

## Personal-site appearance and QQ login

The management UI reuses locally bundled background and service assets from the administrator's personal site, with glass panels, responsive service groups and existing system/light/dark theme preferences. Login and business logs share this appearance. Styling must preserve the current server identity checks and action confirmation behavior.

NapCat login information is restricted to the same authenticated management access and configured NapCat target. It reports recognized events from the current container start, their timestamps, the latest check time and container start time. Advisory text about a future successful login must not be treated as success. Absence of recent login events means unknown, not offline. QQ login events do not establish OneBot connectivity or AstrBot message processing.

The QR image comes only from NapCat's confirmed fixed cache path, is PNG, is size-bounded and must correspond to a recent QR event after the current container start. A conservative 120-second display window is used; this is not a guarantee of QQ server validity. Failure, logout, success, expiry or a newer QR event invalidates the previous image. The browser clears expired images and polls while the panel is visible. Closing the panel releases its image. The response is uncached, and QR images/URLs are never written to action records or durable evidence. Refresh is read-only and does not restart NapCat.

The fixed navigation reserves space above all page content and scroll destinations, including on phones. Both themes use a translucent glass header with 68% background opacity. Shared card surfaces use 70% background opacity in light mode and 80% in dark mode, with blur and readable foreground text. Service information retains its hierarchy, and login event times use the browser locale. NapCat login/QR and selected NapCat business-log panels appear directly beneath its service card. Other service logs keep their existing page position.

Login detection classifies startup, WebUI, QR, login and post-login message structures before interpreting their text. Recognized post-login adapter initialization or genuine send/receive message events establish a logged-in state. Quoted message content must not impersonate login failure, logout or WebUI credentials. The newest event wins, and a new container start invalidates older evidence.

When the requested login or WebUI information is absent, logs are read backwards in successive 200-line extensions of the tail window, inspecting only newly retrieved earlier timestamped records, bounded by the current container start. Search stops once the required structure/event is found or the available history is exhausted. A request time limit preserves responsiveness; missing or incomplete evidence remains unknown and may be retried. QR scan confirmation can look further back for its related QR event without replacing the newer login state.

An explicit button retrieves the current WebUI token from its own WebUI log structure and copies it to the browser clipboard. This read-only endpoint uses the same authenticated access list, fixed NapCat target and uncached JSON policy. This is the only intentional credential response; snapshots and ordinary logs continue to redact credentials. The UI shows only copy success/failure, never the token, and does not persist it or include it in action records. A stopped container cannot return a previous token.
