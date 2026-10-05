package servicemonitor

import (
	"context"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

func TestSystemAccessAndRanges(t *testing.T) {
	m := testMonitor()
	m.cfg.ServiceMonitor.Command = []string{"sh", "-c", `printf '%s' '{"metrics":{}}'`}
	for _, item := range []struct {
		method, path, key string
		code              int
	}{
		{"GET", "/service-monitor/system", "", 403},
		{"POST", "/service-monitor/system", "test-only-key", 405},
		{"GET", "/service-monitor/system?range=7d", "test-only-key", 400},
		{"GET", "/service-monitor/system?command=id", "test-only-key", 400},
		{"GET", "/service-monitor/system?range=1h&range=24h", "test-only-key", 400},
		{"GET", "/service-monitor/system?range=1h", "test-only-key", 200},
		{"GET", "/service-monitor/system?range=6h", "test-only-key", 200},
		{"GET", "/service-monitor/system?range=24h", "test-only-key", 200},
	} {
		req := httptest.NewRequestWithContext(context.Background(), item.method, item.path, nil)
		req.Header.Set("Authorization", "Bearer "+item.key)
		response := httptest.NewRecorder()
		m.ServeHTTP(response, req)
		if response.Code != item.code || response.Header().Get("Cache-Control") != "no-store" {
			t.Fatalf("%s %s: got %d, want %d", item.method, item.path, response.Code, item.code)
		}
	}
}

func TestSystemCache(t *testing.T) {
	m := testMonitor()
	m.cfg.ServiceMonitor.Command = []string{"sh", "-c", `printf '%s' '{"metrics":{"cpu":{}}}'`}
	first := m.systemHistory(context.Background(), "1h")
	m.cfg.ServiceMonitor.Command = []string{"sh", "-c", "exit 1"}
	second := m.systemHistory(context.Background(), "1h")
	if second.Error != "" || first.CollectedAt != second.CollectedAt {
		t.Fatal("repeated visits must share the successful one-minute cache")
	}
}

func TestSystemStaleFailure(t *testing.T) {
	m := testMonitor()
	m.cfg.ServiceMonitor.Command = []string{"sh", "-c", `printf '%s' '{"metrics":{"cpu":{}}}'`}
	first := m.systemHistory(context.Background(), "1h")
	m.cfg.ServiceMonitor.Command = []string{"sh", "-c", "exit 1"}
	m.system["1h"] = systemSample{sample: first, AttemptedAt: time.Now().Add(-2 * time.Minute)}
	failed := m.systemHistory(context.Background(), "1h")
	if failed.Error == "" || failed.CollectedAt != first.CollectedAt || string(failed.Data) != string(first.Data) {
		t.Fatal("cloud failures must retain the last successful data and timestamp")
	}
}

func TestSystemInvalidOutputDoesNotLeak(t *testing.T) {
	m := testMonitor()
	m.cfg.ServiceMonitor.Command = []string{"sh", "-c", "printf private-invalid-output"}
	response := httptest.NewRecorder()
	req := httptest.NewRequestWithContext(context.Background(), "GET", "/service-monitor/system", nil)
	req.Header.Set("Authorization", "Bearer test-only-key")
	m.ServeHTTP(response, req)
	if response.Code != 502 || strings.Contains(response.Body.String(), "private-invalid-output") {
		t.Fatal("invalid output must fail without returning raw cloud diagnostics")
	}
}
