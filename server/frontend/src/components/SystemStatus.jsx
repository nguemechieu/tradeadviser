import { useEffect, useState } from 'react';
import axiosInstance from '../api/axiosConfig';
import '../app.css';

const SystemStatus = () => {
    const [health, setHealth] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [lastUpdated, setLastUpdated] = useState(null);

    const getStatusColor = (status) => {
        if (!status) return '#8ea3bc';
        const statusLower = status.toLowerCase();
        if (statusLower === 'healthy' || statusLower === 'up' || statusLower === 'online') return '#67e2a3';
        if (statusLower === 'degraded' || statusLower === 'warning') return '#f7b666';
        if (statusLower === 'unhealthy' || statusLower === 'down' || statusLower === 'offline') return '#ff7d8d';
        return '#8ea3bc';
    };

    const getStatusIcon = (status) => {
        if (!status) return '⊘';
        const statusLower = status.toLowerCase();
        if (statusLower === 'healthy' || statusLower === 'up' || statusLower === 'online') return '✓';
        if (statusLower === 'degraded' || statusLower === 'warning') return '⚠';
        if (statusLower === 'unhealthy' || statusLower === 'down' || statusLower === 'offline') return '✗';
        return '⊘';
    };

    const fetchHealth = async () => {
        try {
            setLoading(true);
            setError('');
            const response = await axiosInstance.get('/operations/health');
            setHealth(response.data);
            setLastUpdated(new Date());
        } catch (err) {
            setError('Failed to fetch system status. ' + (err.response?.data?.detail || err.message));
            console.error('Health check error:', err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchHealth();
        const interval = setInterval(fetchHealth, 30000); // Refresh every 30 seconds
        return () => clearInterval(interval);
    }, []);

    const StatusCard = ({ title, data, icon }) => (
        <div className="card" style={{ marginBottom: '1.5rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                <h3 style={{ margin: 0, fontSize: '1.1rem' }}>{icon} {title}</h3>
                {data?.status && (
                    <span style={{
                        color: getStatusColor(data.status),
                        fontWeight: 'bold',
                        fontSize: '0.9rem',
                        textTransform: 'uppercase'
                    }}>
                        {data.status}
                    </span>
                )}
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
                {data && Object.entries(data).filter(([key]) => key !== 'status').map(([key, value]) => (
                    <div key={key} style={{ padding: '0.75rem', backgroundColor: 'rgba(83, 180, 255, 0.05)', borderRadius: '4px' }}>
                        <div style={{ color: '#8ea3bc', fontSize: '0.85rem', textTransform: 'capitalize' }}>
                            {key.replace(/_/g, ' ')}
                        </div>
                        <div style={{ color: '#fff', fontSize: '1.1rem', fontWeight: '600', marginTop: '0.25rem' }}>
                            {typeof value === 'object' ? JSON.stringify(value) : String(value)}
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );

    return (
        <section style={{ padding: '2rem' }}>
            <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
                {/* Header */}
                <div style={{ marginBottom: '2rem' }}>
                    <h1 style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>System Status</h1>
                    <p style={{ color: '#8ea3bc', marginBottom: '1rem' }}>
                        Real-time monitoring of all TradeAdviser services
                    </p>
                    <button
                        onClick={fetchHealth}
                        disabled={loading}
                        className="btn btn-primary"
                        style={{ marginRight: '1rem' }}
                    >
                        {loading ? 'Refreshing...' : 'Refresh Now'}
                    </button>
                    {lastUpdated && (
                        <span style={{ color: '#8ea3bc', fontSize: '0.9rem' }}>
                            Last updated: {lastUpdated.toLocaleTimeString()}
                        </span>
                    )}
                </div>

                {/* Error Message */}
                {error && (
                    <div className="error-message" style={{ marginBottom: '2rem' }}>
                        {error}
                    </div>
                )}

                {/* Loading State */}
                {loading && !health && (
                    <div className="card" style={{ textAlign: 'center', padding: '2rem' }}>
                        <p>Loading system status...</p>
                    </div>
                )}

                {/* Overall Status */}
                {health && (
                    <>
                        <div className="card" style={{ marginBottom: '2rem', padding: '1.5rem', borderLeft: `4px solid ${getStatusColor(health.status)}` }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <div>
                                    <div style={{ fontSize: '0.9rem', color: '#8ea3bc', marginBottom: '0.5rem' }}>Overall Status</div>
                                    <h2 style={{ margin: 0, fontSize: '2rem', color: getStatusColor(health.status) }}>
                                        {getStatusIcon(health.status)} {health.status || 'Unknown'}
                                    </h2>
                                </div>
                            </div>
                        </div>

                        {/* Services Grid */}
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '1.5rem', marginBottom: '2rem' }}>
                            {/* Database */}
                            {health.services?.database && (
                                <div className="card">
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
                                        <span style={{ color: getStatusColor(health.services.database.status), fontSize: '1.5rem' }}>
                                            {getStatusIcon(health.services.database.status)}
                                        </span>
                                        <h3 style={{ margin: 0 }}>Database</h3>
                                    </div>
                                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                                        <div>
                                            <div style={{ color: '#8ea3bc', fontSize: '0.85rem' }}>Status</div>
                                            <div style={{ color: getStatusColor(health.services.database.status), fontWeight: 'bold' }}>
                                                {health.services.database.status}
                                            </div>
                                        </div>
                                        {health.services.database.response_ms && (
                                            <div>
                                                <div style={{ color: '#8ea3bc', fontSize: '0.85rem' }}>Response Time</div>
                                                <div style={{ color: '#53b4ff', fontWeight: 'bold' }}>
                                                    {health.services.database.response_ms}ms
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            )}

                            {/* API */}
                            {health.services?.api && (
                                <div className="card">
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
                                        <span style={{ color: getStatusColor(health.services.api.status), fontSize: '1.5rem' }}>
                                            {getStatusIcon(health.services.api.status)}
                                        </span>
                                        <h3 style={{ margin: 0 }}>API Server</h3>
                                    </div>
                                    <div>
                                        <div style={{ color: '#8ea3bc', fontSize: '0.85rem', marginBottom: '0.5rem' }}>Status</div>
                                        <div style={{ color: getStatusColor(health.services.api.status), fontWeight: 'bold', marginBottom: '0.5rem' }}>
                                            {health.services.api.status}
                                        </div>
                                        {health.services.api.response_ms && (
                                            <>
                                                <div style={{ color: '#8ea3bc', fontSize: '0.85rem', marginBottom: '0.25rem' }}>Response Time</div>
                                                <div style={{ color: '#53b4ff', fontWeight: 'bold', marginBottom: '0.5rem' }}>
                                                    {health.services.api.response_ms}ms
                                                </div>
                                            </>
                                        )}
                                        {health.services.api.connections !== undefined && (
                                            <>
                                                <div style={{ color: '#8ea3bc', fontSize: '0.85rem', marginBottom: '0.25rem' }}>Active Connections</div>
                                                <div style={{ color: '#53b4ff', fontWeight: 'bold' }}>
                                                    {health.services.api.connections}
                                                </div>
                                            </>
                                        )}
                                    </div>
                                </div>
                            )}

                            {/* WebSocket */}
                            {health.services?.websocket && (
                                <div className="card">
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
                                        <span style={{ color: getStatusColor(health.services.websocket.status), fontSize: '1.5rem' }}>
                                            {getStatusIcon(health.services.websocket.status)}
                                        </span>
                                        <h3 style={{ margin: 0 }}>WebSocket</h3>
                                    </div>
                                    <div>
                                        <div style={{ color: '#8ea3bc', fontSize: '0.85rem', marginBottom: '0.5rem' }}>Status</div>
                                        <div style={{ color: getStatusColor(health.services.websocket.status), fontWeight: 'bold', marginBottom: '0.5rem' }}>
                                            {health.services.websocket.status}
                                        </div>
                                        {health.services.websocket.clients !== undefined && (
                                            <>
                                                <div style={{ color: '#8ea3bc', fontSize: '0.85rem', marginBottom: '0.25rem' }}>Connected Clients</div>
                                                <div style={{ color: '#53b4ff', fontWeight: 'bold' }}>
                                                    {health.services.websocket.clients}
                                                </div>
                                            </>
                                        )}
                                    </div>
                                </div>
                            )}
                        </div>

                        {/* Detailed Information */}
                        {health.services?.broker && (
                            <StatusCard title="Broker Connections" data={health.services.broker} icon="🔗" />
                        )}
                    </>
                )}
            </div>
        </section>
    );
};

export default SystemStatus;
