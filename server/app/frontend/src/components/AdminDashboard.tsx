import React from "react";
import { Box, Typography, Grid, Paper, Button } from "@mui/material";
import { useNavigate } from "react-router-dom";
import {
    PeopleAlt,
    Assignment,
    Settings,
    BarChart,
    VerifiedUser,
    HelpOutline
} from "@mui/icons-material";

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
                '&:hover': {
                    backgroundColor: "#f4f6f8",
                },
            }}
            onClick={() => navigate(link)}
        >
            <Box sx={{ fontSize: 40, mb: 1 }}>{icon}</Box>
            <Typography variant="h6" fontWeight={600}>{title}</Typography>
        </Paper>
    );
};

const AdminDashboard = () => {
    return (
        <Box sx={{ p: 4 }}>
            <Typography variant="h4" fontWeight={700} gutterBottom color="primary">
                Admin Dashboard
            </Typography>
            <Typography variant="subtitle1" gutterBottom color="text.secondary">
                Manage users, monitor performance, and control application settings.
            </Typography>

            <Grid spacing={3} mt={2}>
                <Grid >
                    <DashboardCard title="Manage Users" icon={<PeopleAlt />} link="/admin/users" />
                </Grid>
                <Grid >
                    <DashboardCard title="Service Requests" icon={<Assignment />} link="/admin/requests" />
                </Grid>
                <Grid >
                    <DashboardCard title="App Settings" icon={<Settings />} link="/admin/settings" />
                </Grid>
                <Grid >
                    <DashboardCard title="Analytics" icon={<BarChart />} link="/admin/analytics" />
                </Grid>
                <Grid >
                    <DashboardCard title="Access Control" icon={<VerifiedUser />} link="/admin/roles" />
                </Grid>
            </Grid>

            <Box textAlign="center" mt={4}>
                <Button variant="outlined" color="primary" href="/help">
                    <HelpOutline sx={{ mr: 1 }} /> Help Center
                </Button>
            </Box>
        </Box>
    );
};

export default AdminDashboard;
