import React, { useState, useEffect } from 'react';

const SEVERITY_CONFIG = {
  critical: { color: '#dc2626', bg: '#fecaca', label: 'Critical' },
  high:     { color: '#ea580c', bg: '#fed7aa', label: 'High' },
  medium:   { color: '#ca8a04', bg: '#fef08a', label: 'Medium' },
  low:      { color: '#2563eb', bg: '#bfdbfe', label: 'Low' },
};
const STATUSES = ['new', 'investigating', 'resolved', 'dismissed'];
const API = 'http://localhost:8000';

export default function App() {
  const [incidents, setIncidents] = useState([]);
  const [severityFilter, setSeverityFilter] = useState(null);
  const [statusFilter, setStatusFilter] = useState(null);
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const params = new URLSearchParams();
    if (severityFilter) params.set('severity', severityFilter);
    if (statusFilter) params.set('status', statusFilter);
    setLoading(true);
    fetch(`${API}/incidents?${params}`)
      .then(r => r.json())
      .then(data => { setIncidents(data); setLoading(false); })
      .catch(() => { setIncidents(mockData()); setLoading(false); });
  }, [severityFilter, statusFilter]);

  const updateStatus = async (id, status) => {
    try {
      await fetch(`${API}/incidents/${id}/status`, {
        method: 'PATCH', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status }),
      });
    } catch {}
    setIncidents(prev => prev.map(i => i.id === id ? { ...i, status } : i));
    if (selected?.id === id) setSelected(prev => ({ ...prev, status }));
  };

  const filtered = incidents;
  const sev = SEVERITY_CONFIG;

  return (
    <div style={{ fontFamily: 'system-ui, sans-serif', maxWidth: 1200, margin: '0 auto', padding: 24 }}>
      <h1 style={{ margin: '0 0 20px' }}>Incident Triage Dashboard</h1>
      <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap', alignItems: 'center' }}>
        <span style={{ fontWeight: 600 }}>Severity:</span>
        <FilterBtn active={!severityFilter} onClick={() => setSeverityFilter(null)}>All</FilterBtn>
        {Object.entries(sev).map(([key, cfg]) => (
          <FilterBtn key={key} active={severityFilter === key}
            onClick={() => setSeverityFilter(severityFilter === key ? null : key)}
            style={{ borderColor: cfg.color, color: cfg.color }}>
            {cfg.label}
          </FilterBtn>
        ))}
        <span style={{ fontWeight: 600, marginLeft: 16 }}>Status:</span>
        <FilterBtn active={!statusFilter} onClick={() => setStatusFilter(null)}>All</FilterBtn>
        {STATUSES.map(s => (
          <FilterBtn key={s} active={statusFilter === s}
            onClick={() => setStatusFilter(statusFilter === s ? null : s)}>
            {s}
          </FilterBtn>
        ))}
      </div>
      {loading ? <p>Loading...</p> : (
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
          <thead>
            <tr style={{ background: '#f1f5f9', textAlign: 'left' }}>
              <th style={thS}>ID</th><th style={thS}>Severity</th><th style={thS}>Status</th>
              <th style={thS}>Title</th><th style={thS}>Source</th><th style={thS}>Alerts</th><th style={thS}>Created</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map(inc => {
              const c = sev[inc.severity] || sev.low;
              return (
                <tr key={inc.id} onClick={() => setSelected(inc)}
                  style={{ cursor: 'pointer', borderBottom: '1px solid #e2e8f0' }}>
                  <td style={tdS}>{inc.id.slice(0,8)}</td>
                  <td style={tdS}><span style={{
                    background: c.bg, color: c.color, padding: '2px 8px',
                    borderRadius: 4, fontWeight: 600, fontSize: 12
                  }}>{c.label}</span></td>
                  <td style={tdS}>{inc.status}</td>
                  <td style={{ ...tdS, maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{inc.title}</td>
                  <td style={tdS}>{inc.source}</td>
                  <td style={tdS}>{inc.alerts_count}</td>
                  <td style={tdS}>{new Date(inc.created_at).toLocaleString()}</td>
                </tr>
              );
            })}
            {filtered.length === 0 && <tr><td colSpan={7} style={{ ...tdS, textAlign: 'center' }}>No incidents found</td></tr>}
          </tbody>
        </table>
      )}
      {selected && <DetailPanel incident={selected} onClose={() => setSelected(null)} onUpdate={updateStatus} />}
    </div>
  );
}

function FilterBtn({ active, children, onClick, style }) {
  return (
    <button onClick={onClick} style={{
      padding: '4px 12px', borderRadius: 4, border: '1px solid #cbd5e1',
      background: active ? '#e2e8f0' : '#fff', cursor: 'pointer', fontSize: 13, ...style
    }}>{children}</button>
  );
}

function DetailPanel({ incident: inc, onClose, onUpdate }) {
  const c = SEVERITY_CONFIG[inc.severity] || SEVERITY_CONFIG.low;
  return (
    <div style={{
      position: 'fixed', top: 0, right: 0, width: 420, height: '100vh',
      background: '#fff', boxShadow: '-4px 0 20px rgba(0,0,0,0.1)',
      padding: 24, overflowY: 'auto', zIndex: 50
    }}>
      <button onClick={onClose} style={{ float: 'right', background: 'none', border: 'none', fontSize: 20, cursor: 'pointer' }}>✕</button>
      <h2 style={{ marginTop: 0 }}>{inc.title}</h2>
      <p><span style={{ background: c.bg, color: c.color, padding: '2px 8px', borderRadius: 4, fontWeight: 600 }}>{c.label}</span></p>
      <p><strong>Status:</strong> {inc.status}</p>
      <p><strong>Source:</strong> {inc.source}</p>
      <p><strong>Correlated Alerts:</strong> {inc.alerts_count}</p>
      <p><strong>Created:</strong> {new Date(inc.created_at).toLocaleString()}</p>
      {inc.assignee && <p><strong>Assignee:</strong> {inc.assignee}</p>}
      {inc.description && <p><strong>Description:</strong><br/>{inc.description}</p>}
      <div style={{ marginTop: 16, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {STATUSES.filter(s => s !== inc.status).map(s => (
          <button key={s} onClick={() => onUpdate(inc.id, s)} style={{
            padding: '6px 14px', borderRadius: 4, border: '1px solid #94a3b8',
            background: '#f8fafc', cursor: 'pointer', fontSize: 13
          }}>Mark {s}</button>
        ))}
      </div>
    </div>
  );
}

function mockData() {
  const sevs = ['critical','high','medium','low'];
  const stats = ['new','investigating','resolved','dismissed'];
  return Array.from({ length: 12 }, (_, i) => ({
    id: `inc-${String(i+1).padStart(3,'0')}-${Math.random().toString(36).slice(2,6)}`,
    title: ['High CPU on web-01','DB connection pool exhausted','API latency spike >2s',
      'Disk usage critical on node-03','Auth service 5xx errors','Memory leak in worker',
      'SSL cert expiring soon','Queue backlog growing','Cache miss rate elevated',
      'Network packet loss detected','Deployment rollback triggered','Rate limit threshold breached'][i],
    severity: sevs[i % 4], status: stats[i % 4], source: ['prometheus','datadog','cloudwatch','pagerduty'][i % 4],
    alerts_count: Math.floor(Math.random() * 20) + 1, assignee: i % 3 === 0 ? 'oncall-primary' : null,
    description: 'Correlated alert cluster requiring triage and investigation.',
    created_at: new Date(Date.now() - i * 3600000).toISOString(),
  }));
}

const thS = { padding: '8px 12px', borderBottom: '2px solid #e2e8f0' };
const tdS = { padding: '8px 12px' };