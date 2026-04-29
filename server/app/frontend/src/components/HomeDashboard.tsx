
import { Box, Typography, Grid, Paper, Button } from "@mui/material";
import { useNavigate } from "react-router-dom";
import {
    Dashboard as DashboardIcon,
    Settings,
    Person,
    Build,
    Chat,
    Store,
} from "@mui/icons-material";
import VerifyLink from "./VerifyLink";


const DashboardCard = ({ title, icon, link }) => {
    const navigate = useNavigate();

    return (
        <Paper
            elevation={3}
            sx={{
                p: 3,
                borderRadius: 4,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                textAlign: "center",
                height: 180,
                cursor: "pointer",
                transition: "0.3s",
                "&:hover": {
                    backgroundColor: "primary.main",
                    color: "white",
                },
            }}
            onClick={() => navigate(link)}
        >
            <Box sx={{ fontSize: 40, mb: 1 }}>{icon}</Box>
            <Typography variant="h6" fontWeight={600}>
                {title}
            </Typography>
        </Paper>
    );
};

const dashboardItems= [
    { title: "Profile", icon: <Person fontSize="large" />, link: "/profile" },
    { title: "Settings", icon: <Settings fontSize="large" />, link: "/settings" },
    { title: "Chat", icon: <Chat fontSize="large" />, link: "/chat" },
    { title: "Marketplace", icon: <Store fontSize="large" />, link: "/market" },
    { title: "Tasks / Services", icon: <Build fontSize="large" />, link: "/services" },
    { title: "Admin Panel", icon: <DashboardIcon fontSize="large" />, link: "/admin" },
];

const HomeDashboard= () => {
    return (
        <Box sx={{ p: 4 }}>
            <Typography variant="h4" fontWeight={700} gutterBottom color="primary">
                Welcome to Sopotek Dashboard
            </Typography>

            <Typography variant="subtitle1" gutterBottom color="text.secondary">
                Manage your services, account, and more — all in one place.
            </Typography>

            <Grid container spacing={3} mt={2}>
                {dashboardItems.map(({ title, icon, link }) => (
                    <Grid key={title} >
                        <DashboardCard title={title} icon={icon} link={link} />
                    </Grid>
                ))}
            </Grid>

            <Box textAlign="center" mt={4}>
                <Button variant="outlined" color="primary" href="/help">
                    Need Help?
                </Button>
            </Box>

            <Box mt={4}>
                <VerifyLink />
            </Box>
        </Box>
    );
};

export default HomeDashboard;
