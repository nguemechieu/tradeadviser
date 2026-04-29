
import { Box, Typography, Container, Paper, Divider } from "@mui/material";

const PressRelease = () => {
    return (
        <Container maxWidth="md" sx={{ py: 5 }}>
            <Paper elevation={3} sx={{ p: 4, borderRadius: 3 }}>
                <Typography variant="h4" color="primary" fontWeight={700} gutterBottom>
                     Launches Multi-Service Platform for Handyman and IT Solutions
                </Typography>

                <Typography variant="subtitle1" color="text.secondary" gutterBottom>
                    April 2025 | Wilmington, Delaware
                </Typography>

                <Divider sx={{ my: 2 }} />

                <Typography variant="body1" >
                    Sopotek is proud to announce the official launch of its all-in-one service platform, providing high-quality handyman and IT services to homes and businesses across the United States. With a mission to simplify service booking and empower professionals, Sopotek brings technology and reliability under one unified brand.
                </Typography>

                <Typography variant="body1" >
                    The platform offers a wide range of services, from furniture assembly, TV mounting, and light fixture installation to tech support, software setup, and cybersecurity consultations. Customers can schedule services via the Sopotek website or mobile app, with transparent pricing and trusted professionals.
                </Typography>

                <Typography variant="body1" >
                    "We created Sopotek to bridge the gap between everyday tasks and trusted help," said Noel Nguemechieu, CEO and Founder of Sopotek. "Whether it’s setting up your smart home or fixing a leaky faucet, Sopotek is your go-to solution."
                </Typography>

                <Typography variant="body1" >
                    The company is currently expanding its technician network and invites skilled professionals to join the Sopotek partner program. With modern scheduling, fair compensation, and access to real-time customer requests, Sopotek aims to create a better experience for both service providers and clients.
                </Typography>

                <Typography variant="body1">
                    For press inquiries, partnership opportunities, or more information, please contact:
                </Typography>

                <Box mt={3}>
                    <Typography fontWeight={600}>Press Contact</Typography>
                    <Typography>Email: press@sopotek.com</Typography>
                    <Typography>Phone: +1 (302) 317-6610</Typography>
                    <Typography>Website: https://www.sopotek.com</Typography>
                </Box>
            </Paper>
        </Container>
    );
};

export default PressRelease;
