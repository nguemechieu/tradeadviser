import React from "react";
import {
    AppBar,
    Toolbar,
    Typography,
    Button,
    Box,
    IconButton,
} from "@mui/material";
import MenuIcon from "@mui/icons-material/Menu";
import { Link, useNavigate } from "react-router-dom";
import useAuth from "../hooks/useAuth";
import SearchBar from "./SearchBar";

const NavBar: React.FC = () => {
    const { auth, setAuth } = useAuth(); // Assuming setAuth is exposed in your hook
    const navigate = useNavigate();

    // Handle logout
    const handleLogout = () => {
        setAuth({}); // clear auth state
        localStorage.clear()
        navigate("/login"); // redirect to login page
    };

    // Don't render if not logged in
    if (!auth?.accessToken) return null;

    return (
        <AppBar position="sticky" color="primary" enableColorOnDark>
            <Toolbar sx={{ display: "flex", justifyContent: "space-between" }}>
                {/* Left section (menu + title) */}
                <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                    <IconButton
                        edge="start"
                        color="inherit"
                        aria-label="menu"
                        sx={{ display: { xs: "flex", md: "none" } }}
                    >
                        <MenuIcon />
                    </IconButton>

                    <Typography
                        variant="h6"
                        sx={{ cursor: "pointer", fontWeight: 600 }}
                        onClick={() => navigate("/")}
                    >
                        SopoTek
                    </Typography>
                </Box>

                {/* Center search bar */}
                <Box sx={{ flexGrow: 1, maxWidth: 500, mx: 2 }}>
                    <SearchBar
                        onResults={(results: any[]) => {
                            console.log("Search results:", results);
                        }}
                    />
                </Box>

                {/* Right section (nav links + logout) */}
                <Box sx={{ display: { xs: "none", md: "flex" }, gap: 2 }}>
                    <Button color="inherit" component={Link} to="/dashboard">
                        Dashboard
                    </Button>
                    <Button color="inherit" component={Link} to="/market">
                        Market
                    </Button>
                    <Button color="inherit" component={Link} to="/services">
                        Services
                    </Button>
                    <Button color="inherit" component={Link} to="/reservation">
                        Reservation
                    </Button>
                    <Button color="inherit" component={Link} to="/calendar">
                        Calendar
                    </Button>
                    <Button color="inherit" component={Link} to="/map">
                        Map
                    </Button>
                    <Button color="inherit" component={Link} to="/activities">
                        Activities
                    </Button>
                    <Button color="inherit" component={Link} to="/profile">
                        Profile
                    </Button>
                    <Button
                        color="secondary"
                        variant="outlined"
                        onClick={handleLogout}
                        sx={{
                            ml: 2,
                            borderRadius: 2,
                            textTransform: "none",
                            fontWeight: 600,
                        }}
                    >
                        Logout
                    </Button>
                </Box>
            </Toolbar>
        </AppBar>
    );
};

export default NavBar;
