import React, { useState, useEffect } from "react";
import {
    Box,
    TextField,
    MenuItem,
    Button,
    Typography,
    Paper,
    Grid,
} from "@mui/material";
import { useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "react-toastify";
import {axiosPrivate} from "../api/axiosPrivate";



const serviceCategories = [
    "Handyman Services",
    "Electrical Work",
    "IT & Tech Support",
    "Plumbing Services",
    "Home Upgrades",
];

const Booking = () => {
    const [searchParams] = useSearchParams();
    const preselectedCategory = searchParams.get("category");

    const [formData, setFormData] = useState({
        name: "",
        email: "",
        phone: "",
        category: preselectedCategory || "",
        date: "",
        time: "",
        notes: "",
    });

    const [errors, setErrors] = useState("");

    const navigate = useNavigate();

    const handleChange = (e) => {
        setFormData((prev) => ({ ...prev, [e.target.name]: e.target.value }));
    };

    const handleSubmit = async (e) => {
        e.preventDefault();

        if (!formData.name || !formData.email || !formData.phone || !formData.date || !formData.time) {
            toast.error("Please fill out all required fields.");
            setErrors("Please fill out all required fields.");
            return;
        }

        try {
            await axiosPrivate.post("/api/bookings", formData);
            toast.success("Booking submitted successfully!");
            navigate("/thank-you");
        } catch (err) {
            toast.error("Failed to submit booking.");
            setErrors(JSON.stringify(err));
        }
    };

    useEffect(() => {
        if (preselectedCategory) {
            searchParams.set("category", preselectedCategory);
        }
    }, [preselectedCategory, searchParams,errors]);

    return (
        <Box sx={{ p: { xs: 2, sm: 4 } }}>
            <Paper
                elevation={4}
                sx={{
                    p: { xs: 2, sm: 4 },
                    maxWidth: 800,
                    mx: "auto",
                    width: "100%",
                }}
            >
                <Typography variant="h4" gutterBottom>
                    Book a Service
                </Typography>

                <form onSubmit={handleSubmit}>
                    <Grid container spacing={3}>
                        <Grid >
                            <TextField
                                label="Full Name"
                                name="name"
                                fullWidth
                                required
                                value={formData.name}
                                onChange={handleChange}
                            />
                        </Grid>

                        <Grid >
                            <TextField
                                label="Email"
                                name="email"
                                type="email"
                                fullWidth
                                required
                                value={formData.email}
                                onChange={handleChange}
                            />
                        </Grid>

                        <Grid>
                            <TextField
                                label="Phone"
                                name="phone"
                                fullWidth
                                required
                                value={formData.phone}
                                onChange={handleChange}
                            />
                        </Grid>

                        <Grid >
                            <TextField
                                select
                                label="Service Category"
                                name="category"
                                fullWidth
                                required
                                value={formData.category}
                                onChange={handleChange}
                            >
                                {serviceCategories.map((option) => (
                                    <MenuItem key={option} value={option}>
                                        {option}
                                    </MenuItem>
                                ))}
                            </TextField>
                        </Grid>

                        <Grid >
                            <TextField
                                label="Preferred Date"
                                type="date"
                                name="date"
                                fullWidth
                                required

                                value={formData.date}
                                onChange={handleChange}
                            />
                        </Grid>

                        <Grid >
                            <TextField
                                label="Preferred Time"
                                type="time"
                                name="time"
                                fullWidth
                                required

                                value={formData.time}
                                onChange={handleChange}
                            />
                        </Grid>

                        <Grid >
                            <TextField
                                label="Additional Notes"
                                name="notes"
                                multiline
                                rows={4}
                                fullWidth
                                value={formData.notes}
                                onChange={handleChange}
                            />
                        </Grid>

                        <Grid>
                            <Button type="submit" variant="contained" color="primary" fullWidth>
                                Submit Booking
                            </Button>
                        </Grid>
                    </Grid>
                </form>
            </Paper>
        </Box>
    );
};

export default Booking;
