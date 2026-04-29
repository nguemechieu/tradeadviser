import React from "react";
import {Typography, Box, Card, CardContent} from "@mui/material";

const TermsOfService = () => {
    return (
        <><Card ><CardContent>
            <Box>
                <Typography variant="h4" gutterBottom color="primary" fontWeight={700}>
                    Terms of Service
                </Typography>

                <Typography variant="body1" >
                    Welcome to Sopotek. By accessing or using our platform, you agree to be bound by these Terms of Service. Please read them carefully.
                </Typography>

                <Typography variant="h6" gutterBottom fontWeight={600}>
                    1. Acceptance of Terms
                </Typography>
                <Typography variant="body1" >
                    By creating an account, accessing, or using our services, you agree to comply with and be bound by these Terms. If you do not agree, you may not access our services.
                </Typography>

                <Typography variant="h6" gutterBottom fontWeight={600}>
                    2. Privacy Policy
                </Typography>
                <Typography variant="body1" property={'props'}>
                    Your privacy is important to us. Please review our Privacy Policy, which explains how we collect, use, and disclose information about you. By using the service, you consent to our collection and use of your information as outlined.
                </Typography>
            </Box>
        </CardContent>
        </Card></>
    );
};

export default TermsOfService;
