/**
 * Enterprise Data Warehouse Dashboard - Frontend Application
 * Built with React, Recharts, and Tailwind CSS.
 * Acts as the client-facing portal for the DWH API, enforcing UI-level RBAC
 * and visualizing ClickHouse analytical payloads.
 */

import React, { useState, useEffect } from 'react';
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts';
import { 
  LayoutDashboard, ShieldAlert, Database, LogOut, Activity, 
  AlertTriangle, CheckCircle2, Lock, Download
} from 'lucide-react';

const API_BASE_URL = 'http://localhost:8000';
// --- AUTHENTICATION & IDENTITY STATE ---
export default function App() {
  const [token, setToken] = useState(localStorage.getItem('token') || null);
  const [role, setRole] = useState(localStorage.getItem('role') || null);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  // --- APPLICATION DATA STATE ---
  const [dashboardData, setDashboardData] = useState([]);
  const [recordCount, setRecordCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  // --- UI NAVIGATION STATE ---
  const [activeTab, setActiveTab] = useState('analytics'); 
  const [selectedTable, setSelectedTable] = useState('retail_credit');
// Available Data Warehouse Tables for analysis
  const tableOptions = [
    { id: 'retail_credit', name: 'Bireysel Krediler (Retail Credit)' },
    { id: 'retail_payment_plan', name: 'Bireysel Ödeme Planı (Retail Payment)' },
    { id: 'commercial_credit', name: 'Ticari Krediler (Commercial Credit)' },
    { id: 'commercial_payment_plan', name: 'Ticari Ödeme Planı (Commercial Payment)' }
  ];
  // --- MOCKED DLQ STATISTICS ---
  // Note: For MVP/Case purposes, these are hardcoded. 
  // In production, these should be fetched from a dedicated DWH metrics endpoint.
  const dlqStatsMapping = {
    'retail_credit': { quarantined: 2100, iqr: 11 },
    'retail_payment_plan': { quarantined: 2186, iqr: 10 },
    'commercial_credit': { quarantined: 120, iqr: 12 },
    'commercial_payment_plan': { quarantined: 34, iqr: 11 }
  };

  const currentStats = dlqStatsMapping[selectedTable] || { quarantined: 0, iqr: 0 };
  /**
   * Handles user authentication.
   * Sends credentials to the API, retrieves the JWT, decodes the payload
   * to extract RBAC roles, and persists the session in localStorage.
   */
  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      // Format credentials per OAuth2 specifications
      const formData = new URLSearchParams();
      formData.append('username', username);
      formData.append('password', password);

      const response = await fetch(`${API_BASE_URL}/token`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: formData
      });

      if (!response.ok) throw new Error('Invalid credentials.');
      
      const data = await response.json();
      setToken(data.access_token);
      
      try {
        // Decode the middle part of the JWT (Payload) to extract identity claims without backend verification
        const payload = JSON.parse(atob(data.access_token.split('.')[1]));
        setRole(payload.role || 'user');
        localStorage.setItem('role', payload.role || 'user');
      } catch (e) {
        // Fallback role in case of token parsing failure
        setRole('admin'); 
        localStorage.setItem('role', 'admin');
      }
      localStorage.setItem('token', data.access_token);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };
  /**
   * Clears session data from memory and local storage, effectively logging the user out.
  */

  const handleLogout = () => {
    setToken(null);
    setRole(null);
    localStorage.removeItem('token');
    localStorage.removeItem('role');
    setDashboardData([]);
  };

  // Automatically fetch fresh data when the user logs in or switches tables

  useEffect(() => {
    if (token) {
      fetchDashboardData();
    }
  }, [token, selectedTable]);

  /**
   * Fetches analytical payload from the FastAPI backend.
   * Injects the Bearer JWT token for authorization and Row-Level Security evaluation.
  */
  const fetchDashboardData = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${API_BASE_URL}/analytics/data?table=${selectedTable}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });

      // If the token is expired or invalid, force a local logout to secure the UI
      if (response.status === 401) return handleLogout(); 
      
      const responseData = await response.json();
      
      if (responseData && responseData.data && Array.isArray(responseData.data)) {
        
        setDashboardData(responseData.data.slice(0, 1000)); 
        setRecordCount(responseData.record_count || responseData.data.length);
      } else {
        setDashboardData([]);
        setRecordCount(0);
      }
    } catch (err) {
      console.error("Failed to fetch data", err);
      setDashboardData([]);
      setRecordCount(0);
    } finally {
      setLoading(false);
    }
  };

  const getChartDataKey = () => {
    return selectedTable.includes('credit') ? 'kkdf_amount' : 'installment_amount';
  };
  /**
   * Client-side CSV generator.
   * Compiles the DLQ statistics into a memory blob and forces a browser download.
  */

  const handleExportCSV = () => {
    const csvContent = "data:text/csv;charset=utf-8," 
      + "timestamp,table_name,error_type,anomaly_count\n"
      + `2026-05-04 12:00:00,${selectedTable},Format Error,${currentStats.quarantined}\n`
      + `2026-05-04 12:00:00,${selectedTable},IQR Outlier,${currentStats.iqr}`;
      
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `${selectedTable}_DLQ_Report.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // --- RENDER: AUTHENTICATION SCREEN ---
  if (!token) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-900 px-4">
        <div className="max-w-md w-full bg-slate-800 rounded-xl shadow-2xl p-8 border border-slate-700">
          <h2 className="text-3xl font-bold text-center text-white mb-2">Teamsecfin Data Platform</h2>
          <form onSubmit={handleLogin} className="space-y-5 mt-6">
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1">Username</label>
              <input type="text" value={username} onChange={(e) => setUsername(e.target.value)} className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2 text-white outline-none focus:border-blue-500" required />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1">Password</label>
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2 text-white outline-none focus:border-blue-500" required />
            </div>
            <button type="submit" disabled={loading} className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-2.5 rounded-lg">
              Secure Login
            </button>
          </form>
        </div>
      </div>
    );
  }
  // Extract dynamic column headers for the Raw Data table based on the actual API payload
  const rawDataKeys = dashboardData.length > 0 ? Object.keys(dashboardData[0]) : [];
  
  // --- RENDER: MAIN DASHBOARD ---
  return (
    <div className="min-h-screen bg-slate-50 flex">
      <div className="w-64 bg-slate-900 text-white flex flex-col shadow-xl z-10">
        <div className="p-6 border-b border-slate-800">
          <h1 className="text-xl font-bold tracking-tight">Teamsecfin DWH</h1>
          <p className="text-xs text-slate-400 mt-1">Enterprise Analytics</p>
        </div>
        
        <nav className="flex-1 p-4 space-y-2">
          <button onClick={() => setActiveTab('analytics')} className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg font-medium transition-colors ${activeTab === 'analytics' ? 'bg-blue-600/20 text-blue-400 border border-blue-500/20' : 'text-slate-300 hover:bg-slate-800'}`}>
            <LayoutDashboard className="w-5 h-5" /> Analytics
          </button>
          {role === 'Admin' && (
            <button onClick={() => setActiveTab('dlq')} className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg font-medium transition-colors ${activeTab === 'dlq' ? 'bg-blue-600/20 text-blue-400 border border-blue-500/20' : 'text-slate-300 hover:bg-slate-800'}`}>
              <ShieldAlert className="w-5 h-5" /> Data Quality (DLQ)
            </button>
          )}
          <button onClick={() => setActiveTab('explorer')} className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg font-medium transition-colors ${activeTab === 'explorer' ? 'bg-blue-600/20 text-blue-400 border border-blue-500/20' : 'text-slate-300 hover:bg-slate-800'}`}>
            <Database className="w-5 h-5" /> Raw Data Explorer
          </button>
        </nav>

        <div className="p-4 border-t border-slate-800">
          <button onClick={handleLogout} className="w-full flex items-center justify-center gap-2 bg-slate-800 hover:bg-red-500/10 hover:text-red-400 text-slate-300 py-2 rounded-lg transition-colors text-sm font-medium">
            <LogOut className="w-4 h-4" /> Sign Out
          </button>
        </div>
      </div>

      <div className="flex-1 flex flex-col h-screen overflow-hidden">
        <header className="bg-white border-b border-slate-200 px-8 py-5 flex justify-between items-center shrink-0">
          <div>
            <h2 className="text-2xl font-bold text-slate-800 capitalize">{activeTab} Dashboard</h2>
            <p className="text-sm text-slate-500">Real-time insights powered by ClickHouse</p>
          </div>
          <div className="flex gap-4 items-center">
            <select value={selectedTable} onChange={(e) => setSelectedTable(e.target.value)} className="bg-white border border-slate-300 text-slate-700 py-2 px-4 rounded-lg outline-none focus:ring-2 focus:ring-blue-500 font-medium cursor-pointer">
              {tableOptions.map(opt => (
                <option key={opt.id} value={opt.id}>{opt.name}</option>
              ))}
            </select>
          </div>
        </header>

        <main className="flex-1 overflow-auto p-8">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
              <p className="text-sm font-medium text-slate-500 mb-1">Loaded Records (API Limit)</p>
              <h3 className="text-3xl font-bold text-slate-800">{loading ? '...' : dashboardData.length}</h3>
            </div>
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
              <p className="text-sm font-medium text-slate-500 mb-1">Data Quality Status</p>
              <h3 className="text-3xl font-bold text-slate-800">IQR Cleaned</h3>
            </div>
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
              <p className="text-sm font-medium text-slate-500 mb-1">Access Level</p>
              <h3 className="text-3xl font-bold text-slate-800 capitalize">{role}</h3>
            </div>
          </div>

          {activeTab === 'analytics' && (
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
              <div className="mb-6">
                <h3 className="text-lg font-bold text-slate-800 capitalize">{selectedTable.replace(/_/g, ' ')}</h3>
                <p className="text-sm text-slate-500 mt-1">Showing up to 1000 cleaned records.</p>
              </div>
              <div className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={dashboardData}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                    <XAxis dataKey="loan_account_number" tick={{fontSize: 10}} stroke="#64748b" />
                    <YAxis tick={{fontSize: 12}} stroke="#64748b" />
                    <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: 'none', borderRadius: '8px', color: '#fff' }} />
                    <Bar dataKey={getChartDataKey()} fill="#3b82f6" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {activeTab === 'explorer' && (
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
              <div className="p-6 border-b border-slate-200">
                <h3 className="text-lg font-bold text-slate-800">Raw Data Viewer (Top 1000)</h3>
              </div>
              <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="bg-slate-50 text-slate-600 text-sm border-b border-slate-200">
                        {rawDataKeys.map(key => (
                          <th key={key} className="p-4 font-semibold capitalize">{key.replace(/_/g, ' ')}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {dashboardData.map((row, idx) => (
                        <tr key={idx} className="border-b border-slate-100 hover:bg-slate-50 text-sm">
                          {rawDataKeys.map(key => (
                            <td key={key} className="p-4 text-slate-800">{row[key] !== null ? row[key].toString() : '-'}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
              </div>
            </div>
          )}

          {activeTab === 'dlq' && role === 'Admin' && (
            <div className="bg-amber-50 rounded-xl shadow-sm border border-amber-200 p-6">
              <h3 className="text-lg font-bold text-amber-900 mb-4">Data Quality for: {selectedTable.replace(/_/g, ' ')}</h3>
              <div className="space-y-4 mb-6 text-amber-800">
                <p><strong>1. Quarantines (DLQ):</strong> {currentStats.quarantined} records quarantined due to type-casting rules.</p>
                <p><strong>2. IQR Profiling:</strong> {currentStats.iqr} statistical anomalies isolated.</p>
              </div>
              <div className="bg-white p-4 rounded-lg flex justify-between items-center shadow-sm">
                <span className="font-medium text-slate-700">Download Report:</span>
                <button onClick={handleExportCSV} className="bg-amber-600 text-white px-5 py-2.5 rounded-lg font-medium hover:bg-amber-700">
                  Export Log (.CSV)
                </button>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}