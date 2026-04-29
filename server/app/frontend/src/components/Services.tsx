import React from "react";
import {
    Box,
    Typography,
    Grid,
    Paper,
    Button,
} from "@mui/material";
import BuildIcon from "@mui/icons-material/Build";
import ElectricalServicesIcon from "@mui/icons-material/ElectricalServices";
import ComputerIcon from "@mui/icons-material/Computer";
import PlumbingIcon from "@mui/icons-material/Plumbing";
import HouseIcon from "@mui/icons-material/House";
import CleaningServicesIcon from "@mui/icons-material/CleaningServices";
import DeleteIcon from "@mui/icons-material/Delete";
import FormatPaintIcon from "@mui/icons-material/FormatPaint";
import { useNavigate } from "react-router-dom";

const serviceList = [
    {
        title: "Handyman Services",
        slug: "handyman",
        description: "Repairs, installations, furniture assembly, and general maintenance.",
        icon: <BuildIcon fontSize="large" />,
        image: "/images/services/handyman.jpg",
    },
    {
        title: "Electrical Work",
        slug: "electrical",
        description: "Lighting, wiring, outlets, breaker boxes, smart device setup.",
        icon: <ElectricalServicesIcon fontSize="large" />,
        image: "/images/services/electrical.jpg",
    },
    {
        title: "IT & Tech Support",
        slug: "tech-support",
        description: "Networking, PC repair, software setup, diagnostics, consulting.",
        icon: <ComputerIcon fontSize="large" />,
        image: "/images/services/tech-support.jpg",
    },
    {
        title: "Plumbing Services",
        slug: "plumbing",
        description: "Leaks, clogged drains, fixture installations, and more.",
        icon: <PlumbingIcon fontSize="large" />,
        image: "/images/services/plumbing.jpg",
    },
    {
        title: "Home Upgrades",
        slug: "home-upgrades",
        description: "Smart home integration, security system setup, and automation.",
        icon: <HouseIcon fontSize="large" />,
        image: "/images/services/home-upgrades.jpg",
    },
    {
        title: "Painting Services",
        slug: "painting",
        description: "Interior & exterior painting, touch-ups, wall prep, and finishes.",
        icon: <FormatPaintIcon fontSize="large" />,
        image: "/images/services/painting.jpg",
    },
    {
        title: "Cleaning Services",
        slug: "cleaning",
        description: "Residential and commercial cleaning with attention to detail.",
        icon: <CleaningServicesIcon fontSize="large" />,
        image: "/images/services/cleaning.jpg",
    },
    {
        title: "Trash & Junk Removal",
        slug: "trash-removal",
        description: "Garage cleanouts, furniture disposal, and general junk removal.",
        icon: <DeleteIcon fontSize="large" />,
        image: "/images/services/trash-removal.jpg",
    },
];

const Services = () => {
    const navigate = useNavigate();

    return (
        <Box sx={{ padding: 4 }}>
            <Typography variant="h4" fontWeight={600} gutterBottom color="primary">
                Our Services
            </Typography>

            <Typography variant="subtitle1" gutterBottom color="text.secondary">
                Sopotek offers high-quality, tech-powered solutions across multiple service domains.
            </Typography>

            <Grid container spacing={3} mt={2}>
                {serviceList.map((service, index) => (
                    <Grid key={index} >
                        <Paper
                            elevation={4}
                            sx={{
                                p: 2,
                                borderRadius: 4,
                                height: "100%",
                                transition: "0.3s",
                                ":hover": {
                                    boxShadow: 8,
                                    transform: "scale(1.02)"
                                }
                            }}
                        >
                            <img
                                src={service.image}
                                alt={service.title}
                                style={{
                                    width: "100%",
                                    height: 180,
                                    objectFit: "cover",
                                    borderRadius: "10px"
                                }}
                            />
                            <Box sx={{ display: "flex", alignItems: "center", mt: 2, mb: 1 }}>
                                <Box sx={{ mr: 1 }}>{service.icon}</Box>
                                <Typography variant="h6" fontWeight={600}>
                                    {service.title}
                                </Typography>
                            </Box>
                            <Typography variant="body2" color="text.secondary">
                                {service.description}
                            </Typography>
                            <Box mt={2}>
                                <Button
                                    variant="outlined"
                                    fullWidth
                                    onClick={() => navigate(`/services/${service.slug}`)}
                                >
                                    View More
                                </Button>
                            </Box>
                        </Paper>
                    </Grid>
                ))}
            </Grid>
        </Box>
    );
};

export default Services;
