import React from "react";
import { useParams } from "react-router-dom";
import { Typography, Box } from "@mui/material";
import HandymanServices from "./HandymanServices";

const ServiceDetail = () => {
    const { slug } = useParams();

    // Normalize the slug for conditional logic
    const normalizedSlug = slug?.toLowerCase();

    return (
        <Box sx={{ p: 4 }}>
            <Typography variant="h4" gutterBottom>
                {normalizedSlug?.replace("-", " ").toUpperCase()} Details
            </Typography>

            <Typography variant="body1" sx={{ mb: 2 }}>
                This is the detail page for the service: <strong>{slug}</strong>.
            </Typography>

            {/* Conditionally render the appropriate service component */}
            {normalizedSlug === "handyman" && <HandymanServices />}
        {/*    */}
        {/*{normalizedSlug === "plumbing" && <PlumbingServices />}*/}

        </Box>
    );
};

export default ServiceDetail;
