import React from "react";
import { Typography, Box, Button, Grid, Paper } from "@mui/material";

const EmployeeDashboard: React.FC = () => {
    return (
        <Box p={3}>
            <Typography variant="h4" gutterBottom>
                Employee Dashboard
            </Typography>

            <Typography variant="subtitle1" gutterBottom>
                Welcome to your workspace. Here you can manage your assignments, view schedules, and track job performance.
            </Typography>

            <Grid container spacing={3} mt={2}>
                <Grid >
                    <Paper elevation={3} sx={{ p: 2 }}>
                        <Typography variant="h6">Today's Jobs</Typography>
                        <Typography>View your assigned work orders for the day.</Typography>
                        <Button variant="contained" size="small" sx={{ mt: 1 }}>
                            View Jobs
                        </Button>
                    </Paper>
                </Grid>

                <Grid >
                    <Paper elevation={3} sx={{ p: 2 }}>
                        <Typography variant="h6">Job History</Typography>
                        <Typography>Review completed jobs and time logs.</Typography>
                        <Button variant="contained" size="small" sx={{ mt: 1 }}>
                            View History
                        </Button>
                    </Paper>
                </Grid>

                <Grid >
                    <Paper elevation={3} sx={{ p: 2 }}>
                        <Typography variant="h6">Profile & Settings</Typography>
                        <Typography>Update your contact info and preferences.</Typography>
                        <Button variant="contained" size="small" sx={{ mt: 1 }}>
                            Edit Profile
                        </Button>
                    </Paper>
                </Grid>
            </Grid>
        </Box>
    );
};

export default EmployeeDashboard;
