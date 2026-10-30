package servicemonitor

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/url"
	"slices"
	"time"

	log "github.com/sirupsen/logrus"
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
		http.Error(w, "System monitoring unavailable", http.StatusBadGateway)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(result)
}

func (m *monitor) systemHistory(ctx context.Context, window string) sample {
	// History reads share the sampler's ten-second cadence without triggering collection.
	m.systemMutex.Lock()
	defer m.systemMutex.Unlock()
	if m.system == nil {
		m.system = make(map[string]systemSample)
	}
	cached := m.system[window]
	if time.Since(cached.AttemptedAt) < 10*time.Second {
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
		previous.Error = "System monitoring read failed; displayed data may be stale."
		return previous
	}
	return systemSample{AttemptedAt: previous.AttemptedAt, sample: sample{Data: data, CollectedAt: time.Now().UTC()}}
}

func (m *monitor) sampleSystem(ctx context.Context) {
	if _, err := m.run(ctx, "sample-system"); err != nil {
		log.Warn("Local system monitoring sample failed; inspect the fixed collector through SSH")
	}
}

func (m *monitor) pollSystem(ctx context.Context) {
	ticker := time.NewTicker(10 * time.Second)
	defer ticker.Stop()
	m.sampleSystem(ctx)
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			m.sampleSystem(ctx)
		}
	}
}
