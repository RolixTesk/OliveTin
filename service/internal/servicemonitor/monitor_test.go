package servicemonitor

import (
	"context"
	"encoding/json"
	"errors"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/OliveTin/OliveTin/internal/config"
)

func testMonitor() *monitor {
	cfg := config.DefaultConfig()
	cfg.AuthLocalUsers.Enabled = true
	cfg.AuthLocalUsers.Users = []*config.LocalUser{{Username: "admin", ApiKey: "test-only-key"}}
	cfg.AccessControlLists = []*config.AccessControlList{{Name: "admins", MatchUsernames: []string{"admin"}}}
	cfg.ServiceMonitor.ACLs = []string{"admins"}
	cfg.ServiceMonitor.ServiceIDs = []string{"astrbot"}
	return &monitor{cfg: cfg, sample: sample{Data: json.RawMessage(`{"services":[]}`)}}
}

func TestReadAccessAndFixedTargets(t *testing.T) {
	m := testMonitor()
	for _, item := range []struct {
		method, path, key string
		code              int
	}{
		{"GET", "/service-monitor/status", "", 403},
		{"GET", "/service-monitor/napcat-login", "", 403},
		{"GET", "/service-monitor/napcat-login", "test-only-key", 404},
		{"GET", "/service-monitor/napcat-token", "", 403},
		{"GET", "/service-monitor/napcat-token", "test-only-key", 404},
		{"POST", "/service-monitor/napcat-token", "test-only-key", 405},
		{"GET", "/service-monitor/status", "invalid", 403},
		{"GET", "/service-monitor/status", "test-only-key", 200},
		{"POST", "/service-monitor/status", "test-only-key", 405},
		{"GET", "/service-monitor/logs/../../etc/shadow", "test-only-key", 404},
		{"GET", "/service-monitor/logs/unknown", "test-only-key", 404},
	} {
		req := httptest.NewRequestWithContext(context.Background(), item.method, item.path, nil)
		req.Header.Set("Authorization", "Bearer "+item.key)
		response := httptest.NewRecorder()
		m.ServeHTTP(response, req)
		if response.Code != item.code {
			t.Fatalf("%s %s: got %d, want %d", item.method, item.path, response.Code, item.code)
		}
	}
}

func TestTokenJSON(t *testing.T) {
	m := testMonitor()
	m.cfg.ServiceMonitor.ServiceIDs = []string{"napcat"}
	m.cfg.ServiceMonitor.Command = []string{"sh", "-c", `printf '%s' '{"token":"synthetic-token"}'`}
	req := httptest.NewRequestWithContext(context.Background(), "GET", "/service-monitor/napcat-token", nil)
	req.Header.Set("Authorization", "Bearer test-only-key")
	response := httptest.NewRecorder()
	m.ServeHTTP(response, req)
	if response.Code != 200 || response.Header().Get("Cache-Control") != "no-store" || response.Body.String() != `{"token":"synthetic-token"}` {
		t.Fatal("explicit authenticated token retrieval must return uncached JSON")
	}
}

func TestFailedSamplePreservesTimestampAndReportsStale(t *testing.T) {
	m := testMonitor()
	m.store([]byte(`{"services":[{"id":"astrbot","state":"active"}]}`), nil)
	previous := m.sample.CollectedAt
	m.store(nil, errors.New("contains secret diagnostic"))
	if m.sample.CollectedAt != previous || m.sample.Error == "" {
		t.Fatal("failed collection must retain timestamp and mark stale")
	}
	if m.sample.Error == "contains secret diagnostic" {
		t.Fatal("raw helper errors must not leak into API")
	}
}

func TestLoginJSON(t *testing.T) {
	m := testMonitor()
	m.cfg.ServiceMonitor.ServiceIDs = []string{"napcat"}
	m.cfg.ServiceMonitor.Command = []string{"sh", "-c", `printf '%s' '{"status":"unknown"}'`}
	req := httptest.NewRequestWithContext(context.Background(), "GET", "/service-monitor/napcat-login", nil)
	req.Header.Set("Authorization", "Bearer test-only-key")
	response := httptest.NewRecorder()
	m.ServeHTTP(response, req)
	if response.Code != 200 || response.Header().Get("Cache-Control") != "no-store" || !json.Valid(response.Body.Bytes()) {
		t.Fatal("authenticated login information must be uncached valid JSON")
	}
}

func TestInvalidLoginJSON(t *testing.T) {
	m := testMonitor()
	m.cfg.ServiceMonitor.ServiceIDs = []string{"napcat"}
	req := httptest.NewRequestWithContext(context.Background(), "GET", "/service-monitor/napcat-login", nil)
	req.Header.Set("Authorization", "Bearer test-only-key")
	m.cfg.ServiceMonitor.Command = []string{"sh", "-c", `printf 'private-invalid-output'`}
	response := httptest.NewRecorder()
	m.ServeHTTP(response, req)
	if response.Code != 502 || strings.Contains(response.Body.String(), "private-invalid-output") {
		t.Fatal("invalid helper output must fail without leaking raw diagnostics")
	}
}
