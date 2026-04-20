import React, { useState, useEffect } from 'react';
import axiosInstance from '../api/axiosConfig';
import logo from '../assets/logo.png';
import '../app.css';

const TradeAdviser = () => {
    const [crypto, setCrypto] = useState("bitcoin");
    const [fiat, setFiat] = useState("usd");
    const [cryptoPrice, setCryptoPrice] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [marketData, setMarketData] = useState([]);
    const [loadingMarket, setLoadingMarket] = useState(false);

    const popularCryptos = ['bitcoin', 'ethereum', 'cardano', 'solana', 'ripple', 'polkadot'];
    const fiats = ['usd', 'eur', 'gbp', 'jpy', 'aud', 'cad'];

    // Fetch popular crypto data on component mount
    useEffect(() => {
        fetchMarketData();
    }, []);

    const fetchMarketData = async () => {
        try {
            setLoadingMarket(true);
            const ids = popularCryptos.join(',');
            const response = await axiosInstance.get(
                `https://api.coingecko.com/api/v3/simple/price?ids=${ids}&vs_currencies=usd&include_market_cap=true&include_24hr_vol=true&include_price_change_percentage=true`
            );
            
            const formatted = Object.entries(response.data).map(([crypto, data]) => ({
                name: crypto.charAt(0).toUpperCase() + crypto.slice(1),
                symbol: crypto.toUpperCase(),
                price: data.usd,
                marketCap: data.usd_market_cap,
                volume: data.usd_24h_vol,
                change24h: data.usd_24h_change
            }));
            
            setMarketData(formatted);
        } catch (err) {
            console.error('Error fetching market data:', err);
        } finally {
            setLoadingMarket(false);
        }
    };

    const handleSubmit = async (e) => {
        e.preventDefault();

        if (!crypto || !fiat) {
            setError("Please select both crypto and fiat currencies.");
            return;
        }

        setLoading(true);
        setError(null);
        setCryptoPrice(null);

        try {
            const response = await axiosInstance.get(
                `https://api.coingecko.com/api/v3/simple/price?ids=${crypto.toLowerCase()}&vs_currencies=${fiat.toLowerCase()}&include_market_cap=true&include_24hr_vol=true`
            );
            const data = response.data[crypto.toLowerCase()];

            if (data?.[fiat.toLowerCase()]) {
                setCryptoPrice({
                    price: data[fiat.toLowerCase()],
                    marketCap: data[`${fiat.toLowerCase()}_market_cap`],
                    volume: data[`${fiat.toLowerCase()}_24h_vol`]
                });
            } else {
                setError(`No data found for ${crypto.toUpperCase()} in ${fiat.toUpperCase()}.`);
            }
        } catch (error) {
            setError("Error fetching data. Please check your inputs.");
            console.error(error);
        } finally {
            setLoading(false);
        }
    };

    const handleQuickSelect = async (cryptoSymbol) => {
        setCrypto(cryptoSymbol);
        setLoading(true);
        setError(null);

        try {
            const response = await axiosInstance.get(
                `https://api.coingecko.com/api/v3/simple/price?ids=${cryptoSymbol.toLowerCase()}&vs_currencies=${fiat.toLowerCase()}&include_market_cap=true&include_24hr_vol=true`
            );
            const data = response.data[cryptoSymbol.toLowerCase()];

            if (data?.[fiat.toLowerCase()]) {
                setCryptoPrice({
                    price: data[fiat.toLowerCase()],
                    marketCap: data[`${fiat.toLowerCase()}_market_cap`],
                    volume: data[`${fiat.toLowerCase()}_24h_vol`]
                });
            }
        } catch (error) {
            setError("Error fetching data.");
        } finally {
            setLoading(false);
        }
    };

    return (
        <section className="tradeadviser-page">
            <div className="page-container">
                {/* Header */}
                <div style={{ textAlign: 'center', marginBottom: '3rem' }}>
                    <img src={logo} alt="TradeAdviser" style={{ height: '80px', marginBottom: '1rem' }} />
                    <h1>TradeAdviser</h1>
                    <p style={{ color: '#8ea3bc', fontSize: '1.1rem' }}>Live Cryptocurrency Price Data</p>
                </div>

                {/* Price Converter */}
                <div className="card" style={{ maxWidth: '600px', margin: '0 auto 3rem auto' }}>
                    <h2>Price Converter</h2>
                    <form onSubmit={handleSubmit}>
                        <div className="form-row">
                            <div className="form-field">
                                <label>Cryptocurrency</label>
                                <select value={crypto} onChange={(e) => setCrypto(e.target.value)} className="input-field">
                                    <option value="">Select a cryptocurrency</option>
                                    {popularCryptos.map(c => (
                                        <option key={c} value={c}>
                                            {c.charAt(0).toUpperCase() + c.slice(1)}
                                        </option>
                                    ))}
                                </select>
                            </div>
                            <div className="form-field">
                                <label>Fiat Currency</label>
                                <select value={fiat} onChange={(e) => setFiat(e.target.value)} className="input-field">
                                    {fiats.map(f => (
                                        <option key={f} value={f}>{f.toUpperCase()}</option>
                                    ))}
                                </select>
                            </div>
                        </div>
                        <button type="submit" disabled={loading} className="btn btn-primary" style={{ width: '100%' }}>
                            {loading ? 'Loading...' : 'Get Price'}
                        </button>
                    </form>

                    {error && <div className="error-message">{error}</div>}

                    {cryptoPrice && (
                        <div style={{ marginTop: '2rem', padding: '1.5rem', backgroundColor: 'rgba(83, 180, 255, 0.1)', borderRadius: '8px', border: '1px solid rgba(83, 180, 255, 0.3)' }}>
                            <h3 style={{ color: '#78e6c8', marginBottom: '1rem' }}>
                                {crypto.toUpperCase()} Price
                            </h3>
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                                <div>
                                    <p style={{ color: '#8ea3bc', marginBottom: '0.5rem' }}>Price</p>
                                    <p style={{ fontSize: '1.5rem', fontWeight: 'bold' }}>
                                        {cryptoPrice.price.toLocaleString()} {fiat.toUpperCase()}
                                    </p>
                                </div>
                                {cryptoPrice.marketCap && (
                                    <div>
                                        <p style={{ color: '#8ea3bc', marginBottom: '0.5rem' }}>Market Cap</p>
                                        <p style={{ fontSize: '1.2rem' }}>
                                            {new Intl.NumberFormat('en-US', {
                                                style: 'currency',
                                                currency: fiat.toUpperCase(),
                                                notation: 'compact'
                                            }).format(cryptoPrice.marketCap)}
                                        </p>
                                    </div>
                                )}
                                {cryptoPrice.volume && (
                                    <div>
                                        <p style={{ color: '#8ea3bc', marginBottom: '0.5rem' }}>24h Volume</p>
                                        <p style={{ fontSize: '1.2rem' }}>
                                            {new Intl.NumberFormat('en-US', {
                                                style: 'currency',
                                                currency: fiat.toUpperCase(),
                                                notation: 'compact'
                                            }).format(cryptoPrice.volume)}
                                        </p>
                                    </div>
                                )}
                            </div>
                        </div>
                    )}
                </div>

                {/* Market Data */}
                <div>
                    <h2 style={{ textAlign: 'center', marginBottom: '2rem' }}>Live Market Data (USD)</h2>
                    
                    {loadingMarket ? (
                        <div className="loading">Loading market data...</div>
                    ) : (
                        <div className="home-grid">
                            {marketData.map(crypto => (
                                <div key={crypto.symbol} className="card" onClick={() => handleQuickSelect(crypto.symbol)} style={{ cursor: 'pointer', transition: 'transform 0.3s, border-color 0.3s' }} onMouseEnter={(e) => e.currentTarget.style.transform = 'translateY(-5px)'} onMouseLeave={(e) => e.currentTarget.style.transform = 'translateY(0)'}>
                                    <h3>{crypto.name}</h3>
                                    <p style={{ color: '#78e6c8', fontSize: '1.3rem', fontWeight: 'bold' }}>
                                        ${crypto.price.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                                    </p>
                                    <p style={{ color: crypto.change24h >= 0 ? '#67e2a3' : '#ff7d8d' }}>
                                        24h: {crypto.change24h >= 0 ? '+' : ''}{crypto.change24h.toFixed(2)}%
                                    </p>
                                    <p style={{ color: '#8ea3bc', fontSize: '0.9rem' }}>
                                        Market Cap: {new Intl.NumberFormat('en-US', {
                                            style: 'currency',
                                            currency: 'USD',
                                            notation: 'compact'
                                        }).format(crypto.marketCap || 0)}
                                    </p>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </section>
    );
};

export default TradeAdviser;
