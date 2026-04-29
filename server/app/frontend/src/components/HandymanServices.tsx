import React from "react";
import {
    Box,
    Typography,
    Grid,
    Paper,
    Button,
    Card,
    CardMedia,
    CardContent,
    Rating,
    Chip,
} from "@mui/material";
import BuildIcon from "@mui/icons-material/Build";
import { useNavigate } from "react-router-dom";

const handymanTasks = [
    {
        title: "Furniture Assembly",
        image: "/images/handyman/furniture.jpg",
        rating: 4.8,
        price: "$50+",
    },
    {
        title: "TV Mounting & Shelving",
        image: "/images/handyman/tv-mounting.jpg",
        rating: 4.7,
        price: "$75+",
    },
    {
        title: "Home Repairs & Fixtures",
        image: "/images/handyman/repairs.jpg",
        rating: 4.9,
        price: "$60+",
    },
    {
        title: "Door, Lock & Handle Repairs",
        image: "/images/handyman/locks.jpg",
        rating: 4.6,
        price: "$40+",
    },
    {
        title: "Drywall Patching",
        image: "/images/handyman/drywall.jpg",
        rating: 4.5,
        price: "$55+",
    },
    {
        title: "Caulking & Weatherproofing",
        image: "/images/handyman/caulking.jpg",
        rating: 4.4,
        price: "$45+",
    },
    {
        title: "Appliance Installation",
        image: "/images/handyman/appliances.jpg",
        rating: 4.9,
        price: "$85+",
    },
];

const HandymanServices = () => {
    const navigate = useNavigate();

    const handleBooking = (service: string | number | boolean) => {
        navigate(`/book-service?category=${encodeURIComponent(service)}`);
    };

    return (
        <Box sx={{ padding: 4 }}>
            <Card sx={{ mb: 4, borderRadius: 4, overflow: "hidden" }}>
                <CardMedia
                    component="img"
                    height="280"
                    image="/images/handyman/banner.jpg"
                    alt="Handyman Banner"
                />
            </Card>

            <Typography variant="h4" fontWeight={600} gutterBottom color="primary">
                Handyman Services
            </Typography>

            <Typography variant="subtitle1" gutterBottom color="text.secondary">
                Reliable and professional help for your everyday home maintenance needs.
            </Typography>

            <Paper elevation={4} sx={{ p: 3, borderRadius: 4, mt: 3 }}>
                <Box display="flex" alignItems="center" mb={2}>
                    <BuildIcon fontSize="large" sx={{ mr: 2 }} />
                    <Typography variant="h6" fontWeight={600}>
                        What We Offer
                    </Typography>
                </Box>

                <Grid container spacing={3}>
                    {handymanTasks.map((task, index) => (
                        <Grid key={index}>
                            <Card
                                sx={{
                                    borderRadius: 3,
                                    height: "100%",
                                    transition: "transform 0.2s ease, box-shadow 0.2s ease",
                                    "&:hover": {
                                        transform: "scale(1.02)",
                                        boxShadow: 6,
                                    },
                                }}
                            >
                                <CardMedia
                                    component="img"
                                    height="160"
                                    image={task.image}
                                    alt={task.title}
                                />
                                <CardContent>
                                    <Typography variant="h6" gutterBottom>
                                        {task.title}
                                    </Typography>

                                    <Box display="flex" alignItems="center" gap={1} mb={1}>
                                        <Rating
                                            name={`rating-${index}`}
                                            value={task.rating}
                                            precision={0.1}
                                            readOnly
                                            size="small"
                                        />
                                        <Typography variant="caption">{task.rating.toFixed(1)}</Typography>
                                    </Box>

                                    <Chip label={`From ${task.price}`} color="primary" variant="outlined" />

                                    <Box mt={2}>
                                        <Button
                                            variant="contained"
                                            fullWidth
                                            onClick={() => handleBooking(task.title)}
                                        >
                                            Book Now
                                        </Button>
                                    </Box>
                                </CardContent>
                            </Card>
                        </Grid>
                    ))}
                </Grid>
            </Paper>
        </Box>
    );
};

export default HandymanServices;
