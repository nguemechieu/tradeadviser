import React, { useState, useEffect } from "react";
import axios from "axios";

const TradeAdviser = () => {
  const [fiat, setFiat] = useState("bitcoin"); // Default fiat currency
  const [cryptoData] = useState([]); // Stores all crypto prices
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function fetchCryptoPrices() {
    try {
      const response = await axios.get(
        `https://api.coingecko.com/api/v3/simple/price?vs_currencies=${fiat}`, // Fetch prices in specified fiat currency
        {
          params: { ids: "all", vs_currencies: "bitcoin" },
        },
      );
      console.log(response.data);
    } catch (error) {
      console.error("Fetch failed", error);
    }
  }

  // Fetch prices when component mounts
  useEffect(() => {
    fetchCryptoPrices()
      .then(() => {
        console.log("Request completed successfully" )
        setLoading(false);
      })
      .catch(() => {
        console.error("Fetch failed");
        setError(
          "An error occurred while fetching crypto prices. Please try again later.",
        );
        setLoading(false);
      });

    // Fetch prices when component mounts
  }); // Re-fetch if fiat currency changes

  return (
    <div className="trade-adviser">
      <h1>Welcome to TradeAdviser</h1>

      <label>
        Fiat Currency:
        <input
          type="text"
          value={fiat}
          onChange={(e) => setFiat(e.target.value.toLowerCase())}
          placeholder="e.g., usd"
        />
      </label>
      <button onClick={fetchCryptoPrices}>Get All Prices</button>

      {loading && <p>Loading...</p>}
      {error && <p style={{ color: "red" }}>Error: {error}</p>}

      {!loading && !error && cryptoData && (
        <table>
          <thead>
            <tr>
              <th>Cryptocurrency</th>
              <th>Price in {fiat.toUpperCase()}</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(cryptoData).map(([crypto, prices]) => (
              <tr key={crypto}>
                <td>{crypto.toUpperCase()}</td>
                <td>{prices[fiat]}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
};

export default TradeAdviser;
