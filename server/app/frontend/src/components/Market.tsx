import React, { useState, useEffect } from "react";
import axios from "axios";
import {
  Box,
  TextField,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  CircularProgress,
} from "@mui/material";
import ArrowDropUpIcon from "@mui/icons-material/ArrowDropUp";
import ArrowDropDownIcon from "@mui/icons-material/ArrowDropDown";

const Market = () => {
  const [cryptos, setCryptos] = useState([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [sortConfig, setSortConfig] = useState({
    key: "market_cap",
    direction: "desc",
  });

  useEffect(() => {
    const fetchCryptos = async () => {
      setLoading(true);
      try {
        const response = await axios.get(
            "https://api.coingecko.com/api/v3/coins/markets",
            {
              params: {
                vs_currency: "usd",
                order: "market_cap_desc",
                per_page: 50,
                page: 1,
              },
            }
        );
        setCryptos(response.data);
      } catch (error) {
        console.error("Error fetching crypto data:", error);
      }
      setLoading(false);
    };

    fetchCryptos();
  }, []);

  const handleSort = (key) => {
    const direction =
        sortConfig.key === key && sortConfig.direction === "asc" ? "desc" : "asc";
    setSortConfig({ key, direction });

    setCryptos((prev) =>
        [...prev].sort((a, b) => {
          if (direction === "asc") return a[key] > b[key] ? 1 : -1;
          else return a[key] < b[key] ? 1 : -1;
        })
    );
  };

  const filteredCryptos = cryptos.filter((crypto) =>
      crypto.name.toLowerCase().includes(search.toLowerCase())
  );

  return (
      <Box sx={{ padding: 4 }}>
        <Typography variant="h4" gutterBottom>
          Cryptocurrency Market
        </Typography>
        <TextField
            label="Search Cryptocurrency"
            fullWidth
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            sx={{ marginBottom: 2 }}
        />

        {loading ? (
            <CircularProgress />
        ) : (
            <TableContainer component={Paper}>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>#</TableCell>
                    <TableCell>Name</TableCell>
                    <TableCell>Symbol</TableCell>
                    <TableCell
                        onClick={() => handleSort("current_price")}
                        style={{ cursor: "pointer" }}
                    >
                      Price (USD)
                      {sortConfig.key === "current_price" &&
                          (sortConfig.direction === "asc" ? (
                              <ArrowDropUpIcon />
                          ) : (
                              <ArrowDropDownIcon />
                          ))}
                    </TableCell>
                    <TableCell
                        onClick={() => handleSort("market_cap")}
                        style={{ cursor: "pointer" }}
                    >
                      Market Cap
                      {sortConfig.key === "market_cap" &&
                          (sortConfig.direction === "asc" ? (
                              <ArrowDropUpIcon />
                          ) : (
                              <ArrowDropDownIcon />
                          ))}
                    </TableCell>
                    <TableCell
                        onClick={() => handleSort("price_change_percentage_24h")}
                        style={{ cursor: "pointer" }}
                    >
                      24h Change (%)
                      {sortConfig.key === "price_change_percentage_24h" &&
                          (sortConfig.direction === "asc" ? (
                              <ArrowDropUpIcon />
                          ) : (
                              <ArrowDropDownIcon />
                          ))}
                    </TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {filteredCryptos.map((crypto, index) => (
                      <TableRow key={crypto.id}>
                        <TableCell>{index + 1}</TableCell>
                        <TableCell>
                          <Box sx={{ display: "flex", alignItems: "center" }}>
                            <img
                                src={crypto.image}
                                alt={crypto.name}
                                style={{ width: 24, height: 24, marginRight: 8 }}
                            />
                            {crypto.name}
                          </Box>
                        </TableCell>
                        <TableCell>{crypto.symbol.toUpperCase()}</TableCell>
                        <TableCell>${crypto.current_price.toLocaleString()}</TableCell>
                        <TableCell>${crypto.market_cap.toLocaleString()}</TableCell>
                        <TableCell
                            style={{
                              color:
                                  crypto.price_change_percentage_24h > 0 ? "green" : "red",
                            }}
                        >
                          {crypto.price_change_percentage_24h.toFixed(2)}%
                        </TableCell>
                      </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
        )}
      </Box>
  );
};

export default Market;
