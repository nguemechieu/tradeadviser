import React from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from 'recharts';

const PerformanceChart = ({ data }) =>
    (
        <div>
          <h3>Portfolio Performance</h3>
          <LineChart width={600} height={300} data={data}>
            <CartesianGrid strokeDasharray="3 3"/>
            <XAxis dataKey="month"/>
            <YAxis/>
            <Tooltip/>
            <Line type="monotone" dataKey="value" stroke="#8884d8"/>
          </LineChart>
        </div>
    );

export default PerformanceChart;
