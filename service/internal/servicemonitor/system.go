package servicemonitor

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/url"
	"slices"
	"time"
)

type systemSample struct {
	AttemptedAt time.Time
	sample
}

func systemRange(query url.Values) (string, bool) {
	if len(query) == 0 {
		return "1h", true
	}
	if len(query) != 1 || len(query["range"]) != 1 {
		return "", false
	}
	window := query.Get("range")
	return window, slices.Contains([]string{"1h", "6h", "24h"}, window)
}

func (m *monitor) serveSystem(w http.ResponseWriter, r *http.Request) {
	window, valid := systemRange(r.URL.Query())
	if !valid {
		http.Error(w, "Unsupported monitoring range", http.StatusBadRequest)
		return
	}
	result := m.systemHistory(r.Context(), window)
	if result.Data == nil {
		http.Error(w, "Cloud monitoring unavailable", http.StatusBadGateway)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(result)
}

func (m *monitor) systemHistory(ctx context.Context, window string) sample {
	// Three fixed windows share a one-minute cache; concurrent visits cannot multiply cloud requests.
	m.systemMutex.Lock()
	defer m.systemMutex.Unlock()
	if m.system == nil {
		m.system = make(map[string]systemSample)
	}
	cached := m.system[window]
	if time.Since(cached.AttemptedAt) < time.Minute {
		return cached.sample
	}
	m.system[window] = m.collectSystem(ctx, window, cached)
	return m.system[window].sample
}

func (m *monitor) collectSystem(ctx context.Context, window string, previous systemSample) systemSample {
	previous.AttemptedAt = time.Now().UTC()
	data, err := m.run(ctx, "system", window)
	if err == nil && !json.Valid(data) {
		err = errors.New("invalid system history")
	}
	if err != nil {
		previous.Error = "Cloud monitoring query failed; displayed data may be stale."
		return previous
	}
	return systemSample{AttemptedAt: previous.AttemptedAt, sample: sample{Data: data, CollectedAt: time.Now().UTC()}}
}
