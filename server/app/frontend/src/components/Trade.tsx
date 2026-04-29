import React from "react";

import OrderPanel from "./OrderPanel";
import {CandlestickChart} from "@mui/icons-material";

const TradingWindow = () => {
  return (
    <div style={{ display: "flex", flexDirection: "row", height: "100vh" }}>
      {/* Chart Section */}
      <div style={{ flex: 3, borderRight: "1px solid #ccc", padding: "10px" }}>
        <CandlestickChart />
      </div>

      {/* Order Panel Section */}
      <div style={{ flex: 1, padding: "10px" }}>
        <OrderPanel />
      </div>
    </div>
  );
};

export default TradingWindow;
