import { useEffect, useState } from "react";
import InvestmentList from "./InvestmentList";
import PerformanceChart from "./PerformanceChart";

const InvestmentPage = () => {
  const [investments] = useState([
    {
      name: "AAPL",
      type: "Stock",
      amountInvested: 1000,
      currentValue: 1500,
      roi: 50,
    },
    {
      name: "Real Estate",
      type: "Property",
      amountInvested: 20000,
      currentValue: 25000,
      roi: 25,
    },
  ]);

  const [performanceData, setPerformanceData] = useState([
    { month: "Jan", value: 20000 },
    { month: "Feb", value: 21000 },
    { month: "Mar", value: 22000 },
    { month: "Apr", value: 23000 },
  ]);
// Generate random monthly performance data for the past year
  const investmentData = [
    {
      month: [
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
      ],
      value: [
        1500, 1600, 1700, 1800, 1900, 2000, 2100, 2200, 2300, 2400, 2500, 2600,
      ],
    },
  ];
  const monthlyPerformance = investmentData.map((data) => ({
    month: data.month,
    value: Math.floor(Math.random() * 1000) + 1000,
  }));
  useEffect(
    () => {
      return setPerformanceData(monthlyPerformance.map.apply);
    },
    [], // Empty array ensures that the effect runs only once on component mounting
  );
  return (
    <div style={{ padding: "20px" }}>
      <h2>Investment Dashboard</h2>
      <div style={{ display: "flex", gap: "20px" }}>
        <InvestmentList investments={investments} />
        <PerformanceChart data={performanceData} />
      </div>
    </div>
  );
};

export default InvestmentPage;
