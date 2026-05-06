import React from "react";
import { Box } from "@mui/material";
import "./Header.css";
import NavBar from "./NavBar";

const Header = () => {
    return (
        <header className="header-container">
            <Box className="header-content">
                {/* Logo Section */}
                <Box className="header-logo-section">
                    <div className="logo-wrapper">
                        <img src="/logo192.png" alt="TradeAdviser Logo" className="logo" />
                    </div>
                    <div className="logo-text">
                        <h1 className="site-title">TradeAdviser</h1>
                        <p className="site-subtitle">Intelligent Trading Advisory Platform</p>
                    </div>
                </Box>

                {/* Navigation */}
                <NavBar />
            </Box>
        </header>
    );
};

export default Header;
