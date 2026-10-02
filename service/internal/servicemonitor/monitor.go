package servicemonitor

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"os/exec"
	"slices"
	"strings"
	"sync"
	"time"

	"connectrpc.com/connect"
	"github.com/OliveTin/OliveTin/internal/auth"
	"github.com/OliveTin/OliveTin/internal/config"
)

const outputLimit = 256 * 1024

type sample struct {
	CollectedAt time.Time       `json:"collectedAt"`
	Error       string          `json:"error,omitempty"`
	Data        json.RawMessage `json:"data"`
}

type monitor struct {
	cfg    *config.Config
	sample sample
	mutex  sync.RWMutex
}

func NewHandler(cfg *config.Config) http.Handler {
	m := &monitor{cfg: cfg, sample: sample{Data: json.RawMessage(`{"services":[]}`)}}
	go m.poll(context.Background())
	return m
}

func (m *monitor) poll(ctx context.Context) {
	interval := time.Duration(max(10, m.cfg.ServiceMonitor.IntervalSeconds)) * time.Second
	ticker := time.NewTicker(interval)
	defer ticker.Stop()
	m.collect(ctx)
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			m.collect(ctx)
		}
	}
}

func (m *monitor) collect(ctx context.Context) {
	data, err := m.run(ctx, "snapshot")
	if err == nil && !json.Valid(data) {
		err = errors.New("invalid monitor snapshot")
	}
	m.store(data, err)
}

func (m *monitor) store(data []byte, err error) {
	m.mutex.Lock()
	defer m.mutex.Unlock()
	if err != nil {
		m.sample.Error = "Service collection failed; displayed data may be stale."
		return
	}
	m.sample = sample{Data: data, CollectedAt: time.Now().UTC()}
}

func (m *monitor) run(ctx context.Context, arguments ...string) ([]byte, error) {
	command := m.cfg.ServiceMonitor.Command
	if len(command) == 0 {
		return nil, errors.New("service monitor command not configured")
	}
	ctx, cancel := context.WithTimeout(ctx, 20*time.Second)
	defer cancel()
	args := append(slices.Clone(command[1:]), arguments...)
	// The command is administrator-owned configuration; HTTP input never selects an executable.
	cmd := exec.CommandContext(ctx, command[0], args...) // #nosec G204 G702
	return boundedOutput(cmd)
}

func boundedOutput(cmd *exec.Cmd) ([]byte, error) {
	stdout, err := cmd.StdoutPipe()
	if err != nil {
		return nil, err
	}
	if err = cmd.Start(); err != nil {
		return nil, err
	}
	data, readErr := io.ReadAll(io.LimitReader(stdout, outputLimit+1))
	if len(data) > outputLimit {
		_ = cmd.Process.Kill()
		_ = cmd.Wait()
		return nil, errors.New("monitor output exceeds limit")
	}
	return waitOutput(cmd, data, readErr)
}

func waitOutput(cmd *exec.Cmd, data []byte, readErr error) ([]byte, error) {
	err := cmd.Wait()
	if readErr != nil {
		return nil, readErr
	}
	return data, err
}

func (m *monitor) authorized(r *http.Request) bool {
	req := connect.NewRequest(&struct{}{})
	for name, values := range r.Header {
		req.Header()[name] = values
	}
	user := auth.UserFromApiCall(r.Context(), req, m.cfg)
	if user.IsGuest() {
		return false
	}
	return hasACL(user.Acls, m.cfg.ServiceMonitor.ACLs)
}

func hasACL(userACLs, allowed []string) bool {
	for _, name := range allowed {
		if slices.Contains(userACLs, name) {
			return true
		}
	}
	return false
}

func (m *monitor) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Cache-Control", "no-store")
	if !m.authorized(r) {
		http.Error(w, "Management login required", http.StatusForbidden)
		return
	}
	if r.Method != http.MethodGet {
		w.Header().Set("Allow", "GET")
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
	m.serveRead(w, r)
}

func (m *monitor) serveRead(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path == "/service-monitor/status" {
		m.mutex.RLock()
		defer m.mutex.RUnlock()
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(m.sample)
		return
	}
	id := strings.TrimPrefix(r.URL.Path, "/service-monitor/logs/")
	if !strings.HasPrefix(r.URL.Path, "/service-monitor/logs/") || !slices.Contains(m.cfg.ServiceMonitor.ServiceIDs, id) {
		http.NotFound(w, r)
		return
	}
	m.serveLogs(w, r, id)
}

func (m *monitor) serveLogs(w http.ResponseWriter, r *http.Request, id string) {
	data, err := m.run(r.Context(), "logs", id)
	if err != nil {
		http.Error(w, "Service logs unavailable", http.StatusBadGateway)
		return
	}
	w.Header().Set("Content-Type", "text/plain; charset=utf-8")
	_, _ = w.Write(data) // #nosec G705 -- text/plain with nosniff; UI renders text, never HTML.
}
