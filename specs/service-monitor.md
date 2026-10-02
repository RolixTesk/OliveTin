# Service monitoring

Service monitoring is optional and disabled unless explicitly enabled by the administrator. It samples the configured, administrator-controlled collector periodically, independently of browser visits. A failed sample preserves the last successful data and timestamp and visibly marks it as stale. Collection has time and output limits.

Only authenticated users belonging to an explicitly allowed access list can read snapshots or business logs. Guest users and authenticated users without this permission cannot access either endpoint. Both endpoints are read-only and responses must not be cached.

Business log targets come from an explicit configured list. Unknown targets and path traversal attempts are rejected before collection. Business logs are bounded and sensitive data is filtered at the collector. They are separate from action execution records.

The service page displays runtime state, boot policy, health, collection time and service-specific details. A running container must not imply successful application login. Unknown or stale business state must be presented as unknown or stale.

After a successful login, an authenticated user can navigate to the service page and reload it without being redirected to login. Guests and unavailable session identities must still be redirected to login. Navigation uses the current server-provided identity, including after login or logout.

Service mutation buttons use the existing authorized action execution mechanism, including confirmations, concurrency limits and execution records. Monitoring does not expose arbitrary command execution, configuration editing or data deletion.
