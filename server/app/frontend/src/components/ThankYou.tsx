// components/ThankYou.tsx
import React from "react";
import { Box, Typography } from "@mui/material";

const ThankYou = () => (
    <Box sx={{ p: 5, textAlign: "center" }}>
        <Typography variant="h4" gutterBottom color="primary">
            🎉 Thank You!
        </Typography>
        <Typography variant="body1">
            Your booking has been received. We'll follow up shortly!
        </Typography>
    </Box>
);

export default ThankYou;
