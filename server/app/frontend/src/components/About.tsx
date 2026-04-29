import React from "react";
import { Card, CardContent, Typography, Container } from "@mui/material";

const About = () => {
    return (
        <Container maxWidth="md" sx={{ py: 5 }}>
            <Card elevation={3}>
                <CardContent>
                    <Typography variant="h4" color="primary" gutterBottom>
                        About Us
                    </Typography>
                    <Typography variant="body1" color="text.secondary">
                        TradeAdviser is a cutting-edge, AI-powered multi-service platform
                        designed to help individuals and businesses manage home and IT
                        needs effortlessly. Our mission is to improve customer experience,
                        reduce service friction, and deliver reliable solutions—from
                        handyman work to tech support—all under one smart, connected
                        ecosystem.
                    </Typography>
                </CardContent>
            </Card>
        </Container>
    );
};

export default About;
