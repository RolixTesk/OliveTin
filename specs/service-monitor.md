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
