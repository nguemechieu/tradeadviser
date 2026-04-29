import React from "react";
import { Box, Typography, Paper, Button, Grid } from "@mui/material";
import { useNavigate } from "react-router-dom";
import {
    Assignment,
    Chat,
    Person,
    Schedule,
    BuildCircle,
} from "@mui/icons-material";

// Card type props

// DashboardCard component
const DashboardCard= ({ title, icon, link }) => {
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
                    backgroundColor: "#f4f6f8",
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

// Card data array
const technicianCards=[
    {
        title: "My Tasks",
        icon: <Assignment fontSize="large" />,
        link: "/technician/tasks",
    },
    {
        title: "Schedule",
        icon: <Schedule fontSize="large" />,
        link: "/technician/schedule",
    },
    {
        title: "Chat",
        icon: <Chat fontSize="large" />,
        link: "/chat",
    },
    {
        title: "Profile",
        icon: <Person fontSize="large" />,
        link: "/profile",
    },
    {
        title: "Skills & Availability",
        icon: <BuildCircle fontSize="large" />,
        link: "/technician/settings",
    },
];

// Main dashboard
const TechnicianDashboard = () => {
    return (
        <Box sx={{ p: 4 }}>
            <Typography variant="h4" fontWeight={700} gutterBottom color="primary">
                Technician Dashboard
            </Typography>

            <Typography variant="subtitle1" gutterBottom color="text.secondary">
                View your schedule, assigned tasks, and update your profile.
            </Typography>

            <Grid container spacing={3} mt={2}>
                {technicianCards.map((card) => (
                    <Grid>
                        <DashboardCard {...card} />
                    </Grid>
                ))}
            </Grid>

            <Box textAlign="center" mt={4}>
                <Button variant="outlined" color="primary" href="/help">
                    Need Help?
                </Button>
            </Box>
        </Box>
    );
};

export default TechnicianDashboard;
