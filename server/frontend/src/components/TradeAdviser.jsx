import React, { useState } from 'react';
import axios from 'axios';

const TradeAdviser = () => {
    const [crypto, setCrypto] = useState("");
    const [fiat, setFiat] = useState("");
    const [cryptoPrice, setCryptoPrice] = useState(0);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [convertedPrice, setConvertedPrice] = useState(null);

    const handleSubmit = async (e) => {
        e.preventDefault();

        // Validate input
        if (!crypto || !fiat) {
            setError("Please enter both crypto and fiat values.");
            return;
        }

        setLoading(true);
        setError(null);
        setConvertedPrice(null);

        try {
            // Format input to lowercase to meet API requirements
            const formattedCrypto = crypto.toLowerCase();
            const formattedFiat = fiat.toLowerCase();
            const response = await axios.get(`https://api.coingecko.com/api/v3/simple/price?ids=${formattedCrypto}&vs_currencies=${formattedFiat}`);
            const price = response.data[formattedCrypto]?.[formattedFiat];

            if (price) {
                setCryptoPrice(price);
                setConvertedPrice(price);
            } else {
                setError(`No data found for ${formattedCrypto.toUpperCase()} in ${formattedFiat.toUpperCase()}.`);
            }
        } catch (error) {
            setError("Error fetching data. Please check your inputs.");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div>
            <h1>Welcome to TradeAdviser</h1>
            {loading ? <p>Loading...</p> : error ? <p>Error: {error}</p> : (
                <>
                    <form onSubmit={handleSubmit}>
                        <label>
                            Crypto:
                            <input
                                type="text"
                                value={crypto}
                                onChange={(e) => setCrypto(e.target.value)}
                                placeholder="e.g., bitcoin"
                            />
                        </label>
                        <br />
                        <label>
                            Fiat:
                            <input
                                type="text"
                                value={fiat}
                                onChange={(e) => setFiat(e.target.value)}
                                placeholder="e.g., usd"
                            />
                        </label>
                        <br />
                        <button type="submit">Get Price</button>
                    </form>

                    {convertedPrice !== null && (
                        <p>The price of 1 {crypto.toUpperCase()} in {fiat.toUpperCase()} is {convertedPrice}</p>
                    )}
                </>
            )}
        </div>
    );
};

export default TradeAdviser;
