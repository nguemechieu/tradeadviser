import { useContext, useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import AuthContext from '../context/AuthProvider';
import axiosInstance from '../api/axiosConfig';
import '../app.css';

const PortfolioPage = () => {
    const { auth } = useContext(AuthContext);
    const navigate = useNavigate();
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [portfolio, setPortfolio] = useState(null);
    const [positions, setPositions] = useState([]);
    const [performance, setPerformance] = useState(null);

    useEffect(() => {
        fetchPortfolioData();
    }, []);

    const fetchPortfolioData = async () => {
        try {
            setLoading(true);
            setError('');

            // Try to fetch portfolio data from backend
            try {
                const response = await axiosInstance.get('/portfolio');
                setPortfolio(response.data);
            } catch (err) {
                // If endpoint doesn't exist, use mock data
                console.warn('Portfolio endpoint not available, using mock data');
                setPortfolio({
                    total_value: auth?.user?.cash_balance || 100000,
                    invested_amount: 45000,
                    cash_balance: (auth?.user?.cash_balance || 100000) - 45000,
                    day_change: 1250.50,
                    day_change_percent: 2.85,
                    all_time_change: 12500.00,
                    all_time_change_percent: 14.29,
                });
            }

            // Mock positions data
            setPositions([
                {
                    id: 1,
                    symbol: 'AAPL',
                    name: 'Apple Inc.',
                    quantity: 50,
                    price: 450.25,
                    value: 22512.50,
                    day_change: 125.50,
                    day_change_percent: 0.56,
                    sector: 'Technology',
                    entry_price: 420.00,
                },
                {
                    id: 2,
                    symbol: 'MSFT',
                    name: 'Microsoft Corporation',
                    quantity: 30,
                    price: 380.75,
                    value: 11422.50,
                    day_change: -95.25,
                    day_change_percent: -0.83,
                    sector: 'Technology',
                    entry_price: 375.00,
                },
                {
                    id: 3,
                    symbol: 'GOOGL',
                    name: 'Alphabet Inc.',
                    quantity: 25,
                    price: 125.50,
                    value: 3137.50,
                    day_change: 50.25,
                    day_change_percent: 1.63,
                    sector: 'Technology',
                    entry_price: 120.00,
                },
                {
                    id: 4,
                    symbol: 'TSLA',
                    name: 'Tesla Inc.',
                    quantity: 15,
                    price: 245.80,
                    value: 3687.00,
                    day_change: 170.00,
                    day_change_percent: 4.83,
                    sector: 'Automotive',
                    entry_price: 230.00,
                },
            ]);

            // Mock performance data
            setPerformance({
                best_performer: { symbol: 'TSLA', change_percent: 4.83 },
                worst_performer: { symbol: 'MSFT', change_percent: -0.83 },
                top_sector: 'Technology',
                sector_allocation: [
                    { sector: 'Technology', percentage: 78.5, value: 35332.50 },
                    { sector: 'Automotive', percentage: 21.5, value: 3687.00 },
                ],
            });
        } catch (err) {
            setError('Failed to load portfolio data');
            console.error('Error fetching portfolio:', err);
        } finally {
            setLoading(false);
        }
    };

    const getColorByPercent = (percent) => {
        if (percent > 0) return '#3cff00';
        if (percent < 0) return '#ff3333';
        return '#8ea3bc';
    };

    if (loading) {
        return (
            <section style={{ padding: '2rem', textAlign: 'center' }}>
                <h2>Loading Portfolio...</h2>
            </section>
        );
    }

    return (
        <section style={{ padding: '2rem', maxWidth: '1400px', margin: '0 auto' }}>
            {/* Header */}
            <div style={{ marginBottom: '2rem' }}>
                <h1 style={{ marginBottom: '0.5rem' }}>Portfolio Overview</h1>
                <p style={{ color: '#8ea3bc' }}>Track and manage your investments</p>
            </div>

            {/* Error Message */}
            {error && (
                <div style={{
                    backgroundColor: '#fee',
                    color: '#c33',
                    padding: '1rem',
                    borderRadius: '4px',
                    marginBottom: '1rem'
                }}>
                    {error}
                </div>
            )}

            {/* Portfolio Summary Cards */}
            {portfolio && (
                <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
                    gap: '1.5rem',
                    marginBottom: '2rem'
                }}>
                    {/* Total Value */}
                    <div className="card" style={{ padding: '1.5rem' }}>
                        <p style={{ color: '#8ea3bc', marginTop: 0, fontSize: '0.9rem' }}>
                            Total Portfolio Value
                        </p>
                        <h2 style={{ color: '#53b4ff', marginTop: 0, marginBottom: '0.5rem' }}>
                            ${portfolio.total_value?.toLocaleString('en-US', { maximumFractionDigits: 2 })}
                        </h2>
                        <p style={{
                            color: getColorByPercent(portfolio.day_change_percent),
                            margin: 0,
                            fontSize: '0.95rem'
                        }}>
                            {portfolio.day_change >= 0 ? '+' : ''}{portfolio.day_change?.toFixed(2)} ({portfolio.day_change_percent?.toFixed(2)}%) today
                        </p>
                    </div>

                    {/* Invested Amount */}
                    <div className="card" style={{ padding: '1.5rem' }}>
                        <p style={{ color: '#8ea3bc', marginTop: 0, fontSize: '0.9rem' }}>
                            Invested Amount
                        </p>
                        <h2 style={{ color: '#ffd93d', marginTop: 0, marginBottom: '0.5rem' }}>
                            ${portfolio.invested_amount?.toLocaleString('en-US', { maximumFractionDigits: 2 })}
                        </h2>
                        <p style={{ color: '#8ea3bc', margin: 0, fontSize: '0.95rem' }}>
                            {portfolio.invested_amount && portfolio.total_value ? 
                                ((portfolio.invested_amount / portfolio.total_value) * 100).toFixed(1) : 0}% of portfolio
                        </p>
                    </div>

                    {/* Cash Balance */}
                    <div className="card" style={{ padding: '1.5rem' }}>
                        <p style={{ color: '#8ea3bc', marginTop: 0, fontSize: '0.9rem' }}>
                            Cash Balance
                        </p>
                        <h2 style={{ color: '#53b4ff', marginTop: 0, marginBottom: '0.5rem' }}>
                            ${portfolio.cash_balance?.toLocaleString('en-US', { maximumFractionDigits: 2 })}
                        </h2>
                        <p style={{ color: '#8ea3bc', margin: 0, fontSize: '0.95rem' }}>
                            Available to invest
                        </p>
                    </div>

                    {/* All-Time Performance */}
                    <div className="card" style={{ padding: '1.5rem' }}>
                        <p style={{ color: '#8ea3bc', marginTop: 0, fontSize: '0.9rem' }}>
                            All-Time Performance
                        </p>
                        <h2 style={{
                            color: getColorByPercent(portfolio.all_time_change_percent),
                            marginTop: 0,
                            marginBottom: '0.5rem'
                        }}>
                            {portfolio.all_time_change >= 0 ? '+' : ''}{portfolio.all_time_change?.toFixed(2)}
                        </h2>
                        <p style={{
                            color: getColorByPercent(portfolio.all_time_change_percent),
                            margin: 0,
                            fontSize: '0.95rem'
                        }}>
                            {portfolio.all_time_change_percent?.toFixed(2)}% return
                        </p>
                    </div>
                </div>
            )}

            {/* Holdings and Performance Grid */}
            <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(500px, 1fr))',
                gap: '2rem',
                marginBottom: '2rem'
            }}>
                {/* Current Holdings */}
                <div className="card" style={{ padding: '2rem' }}>
                    <h2 style={{ marginTop: 0 }}>Current Holdings ({positions.length})</h2>
                    
                    {positions.length === 0 ? (
                        <p style={{ color: '#8ea3bc' }}>No positions in your portfolio</p>
                    ) : (
                        <div style={{ overflowX: 'auto' }}>
                            <table style={{
                                width: '100%',
                                borderCollapse: 'collapse'
                            }}>
                                <thead>
                                    <tr style={{ borderBottom: '2px solid rgba(136, 168, 203, 0.2)' }}>
                                        <th style={{ padding: '0.75rem', textAlign: 'left', fontSize: '0.85rem' }}>Symbol</th>
                                        <th style={{ padding: '0.75rem', textAlign: 'right', fontSize: '0.85rem' }}>Quantity</th>
                                        <th style={{ padding: '0.75rem', textAlign: 'right', fontSize: '0.85rem' }}>Price</th>
                                        <th style={{ padding: '0.75rem', textAlign: 'right', fontSize: '0.85rem' }}>Value</th>
                                        <th style={{ padding: '0.75rem', textAlign: 'right', fontSize: '0.85rem' }}>Day Change</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {positions.map((position) => (
                                        <tr key={position.id} style={{ borderBottom: '1px solid rgba(136, 168, 203, 0.1)' }}>
                                            <td style={{ padding: '0.75rem' }}>
                                                <div>
                                                    <strong>{position.symbol}</strong>
                                                    <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.8rem', color: '#8ea3bc' }}>
                                                        {position.name}
                                                    </p>
                                                </div>
                                            </td>
                                            <td style={{ padding: '0.75rem', textAlign: 'right' }}>
                                                {position.quantity}
                                            </td>
                                            <td style={{ padding: '0.75rem', textAlign: 'right' }}>
                                                ${position.price?.toFixed(2)}
                                            </td>
                                            <td style={{ padding: '0.75rem', textAlign: 'right', fontWeight: '600' }}>
                                                ${position.value?.toLocaleString('en-US', { maximumFractionDigits: 2 })}
                                            </td>
                                            <td style={{
                                                padding: '0.75rem',
                                                textAlign: 'right',
                                                color: getColorByPercent(position.day_change_percent)
                                            }}>
                                                {position.day_change >= 0 ? '+' : ''}{position.day_change?.toFixed(2)}
                                                <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.8rem' }}>
                                                    ({position.day_change_percent?.toFixed(2)}%)
                                                </p>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </div>

                {/* Performance Summary */}
                {performance && (
                    <div className="card" style={{ padding: '2rem' }}>
                        <h2 style={{ marginTop: 0 }}>Performance Summary</h2>

                        {/* Best/Worst Performers */}
                        <div style={{ marginBottom: '2rem' }}>
                            <h3 style={{ marginTop: 0, marginBottom: '1rem' }}>Top Movers</h3>
                            <div style={{ display: 'grid', gap: '1rem' }}>
                                <div style={{
                                    padding: '1rem',
                                    backgroundColor: 'rgba(60, 255, 0, 0.1)',
                                    borderRadius: '4px',
                                    borderLeft: '3px solid #3cff00'
                                }}>
                                    <p style={{ margin: '0 0 0.5rem 0', color: '#8ea3bc', fontSize: '0.9rem' }}>
                                        Best Performer
                                    </p>
                                    <p style={{ margin: 0, color: '#3cff00', fontSize: '1.1rem', fontWeight: '600' }}>
                                        {performance.best_performer.symbol} +{performance.best_performer.change_percent?.toFixed(2)}%
                                    </p>
                                </div>

                                <div style={{
                                    padding: '1rem',
                                    backgroundColor: 'rgba(255, 51, 51, 0.1)',
                                    borderRadius: '4px',
                                    borderLeft: '3px solid #ff3333'
                                }}>
                                    <p style={{ margin: '0 0 0.5rem 0', color: '#8ea3bc', fontSize: '0.9rem' }}>
                                        Worst Performer
                                    </p>
                                    <p style={{ margin: 0, color: '#ff3333', fontSize: '1.1rem', fontWeight: '600' }}>
                                        {performance.worst_performer.symbol} {performance.worst_performer.change_percent?.toFixed(2)}%
                                    </p>
                                </div>
                            </div>
                        </div>

                        {/* Sector Allocation */}
                        <div>
                            <h3 style={{ marginTop: '1rem', marginBottom: '1rem' }}>Sector Allocation</h3>
                            <div style={{ display: 'grid', gap: '1rem' }}>
                                {performance.sector_allocation.map((sector, idx) => (
                                    <div key={idx}>
                                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                                            <span>{sector.sector}</span>
                                            <span style={{ color: '#53b4ff', fontWeight: '600' }}>
                                                {sector.percentage}% (${sector.value?.toLocaleString('en-US', { maximumFractionDigits: 0 })})
                                            </span>
                                        </div>
                                        <div style={{
                                            width: '100%',
                                            height: '8px',
                                            backgroundColor: 'rgba(136, 168, 203, 0.1)',
                                            borderRadius: '4px',
                                            overflow: 'hidden'
                                        }}>
                                            <div style={{
                                                width: `${sector.percentage}%`,
                                                height: '100%',
                                                backgroundColor: '#53b4ff',
                                                transition: 'width 0.3s ease'
                                            }} />
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                )}
            </div>

            {/* Action Buttons */}
            <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
                gap: '1rem',
                marginTop: '2rem'
            }}>
                <button
                    onClick={() => navigate('/trading')}
                    className="btn btn-primary"
                    style={{ padding: '0.75rem' }}
                >
                    📈 Trade
                </button>
                <button
                    onClick={fetchPortfolioData}
                    className="btn btn-secondary"
                    style={{ padding: '0.75rem' }}
                >
                    🔄 Refresh
                </button>
                <button
                    onClick={() => navigate('/dashboard')}
                    className="btn btn-secondary"
                    style={{ padding: '0.75rem' }}
                >
                    📊 Dashboard
                </button>
            </div>
        </section>
    );
};

export default PortfolioPage;
