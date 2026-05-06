import {
    AppBar,
    Toolbar,
    Typography,
    Button,
    Box,
    IconButton,
    Menu,
    MenuItem,
    Divider,
} from "@mui/material";
import MenuIcon from "@mui/icons-material/Menu";
import CloseIcon from "@mui/icons-material/Close";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import DashboardIcon from "@mui/icons-material/Dashboard";
import TrendingUpIcon from "@mui/icons-material/TrendingUp";
import AccountBalanceIcon from "@mui/icons-material/AccountBalance";
import SettingsIcon from "@mui/icons-material/Settings";
import GroupIcon from "@mui/icons-material/Group";
import WarningIcon from "@mui/icons-material/Warning";
import EngineeringIcon from "@mui/icons-material/Engineering";
import LogoutIcon from "@mui/icons-material/Logout";
import AccountCircleIcon from "@mui/icons-material/AccountCircle";
import { Link, useNavigate } from "react-router-dom";
import useAuth from "../hooks/useAuth";
import SearchBar from "./SearchBar";
import { useState } from "react";
import "./NavBar.css";

interface NavMenuItem {
    label: string;
    path: string;
    icon?: React.ReactNode;
    roles: string[];
}

const NavBar: React.FC = () => {
    const { auth, setAuth } = useAuth();
    const navigate = useNavigate();
    const [mobileOpen, setMobileOpen] = useState(false);
    const [tradingAnchor, setTradingAnchor] = useState<null | HTMLElement>(null);
    const [analyticsAnchor, setAnalyticsAnchor] = useState<null | HTMLElement>(null);
    const [adminAnchor, setAdminAnchor] = useState<null | HTMLElement>(null);
    const [moreAnchor, setMoreAnchor] = useState<null | HTMLElement>(null);

    const userRole = auth?.role || '';

    // Menu items organized by category
    const menuItems = {
        trading: [
            { label: "Trading Editor", path: "/trading-editor", icon: <TrendingUpIcon />, roles: ["trader", "admin", "super_admin"] },
            { label: "Signals", path: "/signals", icon: <TrendingUpIcon />, roles: ["trader", "risk_manager", "admin", "super_admin"] },
            { label: "Strategies", path: "/strategies", icon: <TrendingUpIcon />, roles: ["trader", "risk_manager", "admin", "super_admin"] },
            { label: "Backtesting", path: "/backtesting", icon: <TrendingUpIcon />, roles: ["trader", "risk_manager", "admin", "super_admin"] },
        ] as NavMenuItem[],
        portfolio: [
            { label: "Portfolio", path: "/portfolio", icon: <AccountBalanceIcon />, roles: ["trader", "risk_manager", "admin", "super_admin"] },
            { label: "Positions", path: "/positions", icon: <AccountBalanceIcon />, roles: ["trader", "risk_manager", "admin", "super_admin"] },
            { label: "Quant PM", path: "/quant-pm", icon: <AccountBalanceIcon />, roles: ["risk_manager", "admin", "super_admin"] },
        ] as NavMenuItem[],
        analytics: [
            { label: "AI Trade Review", path: "/ai", icon: <TrendingUpIcon />, roles: ["trader", "risk_manager", "admin", "super_admin"] },
            { label: "Risk Management", path: "/risk", icon: <WarningIcon />, roles: ["risk_manager", "admin", "super_admin"] },
            { label: "Performance Audit", path: "/audit", icon: <TrendingUpIcon />, roles: ["admin", "super_admin"] },
        ] as NavMenuItem[],
        admin: [
            { label: "Operations", path: "/operations", icon: <EngineeringIcon />, roles: ["operations", "admin", "super_admin"] },
            { label: "Brokers", path: "/brokers", icon: <AccountBalanceIcon />, roles: ["trader", "operations", "admin", "super_admin"] },
            { label: "Stellar Network", path: "/stellar", icon: <TrendingUpIcon />, roles: ["trader", "operations", "admin", "super_admin"] },
            { label: "AI Agents", path: "/agents", icon: <TrendingUpIcon />, roles: ["admin", "super_admin"] },
            { label: "Users & Licenses", path: "/admin/users-licenses", icon: <GroupIcon />, roles: ["admin", "super_admin"] },
        ] as NavMenuItem[],
    };

    const handleLogout = () => {
        setAuth({});
        localStorage.clear();
        navigate("/login");
    };

    const getVisibleItems = (items: NavMenuItem[]) => {
        return items.filter(item => item.roles.includes(userRole));
    };

    const tradingItems = getVisibleItems(menuItems.trading);
    const portfolioItems = getVisibleItems(menuItems.portfolio);
    const analyticsItems = getVisibleItems(menuItems.analytics);
    const adminItems = getVisibleItems(menuItems.admin);

    // Don't render if not logged in
    if (!auth?.accessToken) return null;

    return (
        <AppBar position="sticky" color="inherit" className="navbar-container">
            <Toolbar className="navbar-toolbar">
                {/* Logo */}
                <Typography
                    variant="h6"
                    className="navbar-logo"
                    onClick={() => navigate("/dashboard")}
                >
                    🚀 TradeAdviser
                </Typography>

                {/* Desktop Navigation */}
                <Box className="navbar-desktop-nav">
                    <Button
                        component={Link}
                        to="/dashboard"
                        className="navbar-nav-btn"
                        startIcon={<DashboardIcon />}
                    >
                        Dashboard
                    </Button>

                    {/* Trading Dropdown */}
                    {tradingItems.length > 0 && (
                        <>
                            <Button
                                className="navbar-nav-btn dropdown-btn"
                                endIcon={<ExpandMoreIcon />}
                                onClick={(e) => setTradingAnchor(e.currentTarget)}
                            >
                                Trading
                            </Button>
                            <Menu
                                anchorEl={tradingAnchor}
                                open={Boolean(tradingAnchor)}
                                onClose={() => setTradingAnchor(null)}
                                className="navbar-menu"
                            >
                                {tradingItems.map((item) => (
                                    <MenuItem
                                        key={item.path}
                                        onClick={() => {
                                            navigate(item.path);
                                            setTradingAnchor(null);
                                        }}
                                        className="navbar-menu-item"
                                    >
                                        {item.icon && <span className="menu-icon">{item.icon}</span>}
                                        {item.label}
                                    </MenuItem>
                                ))}
                            </Menu>
                        </>
                    )}

                    {/* Portfolio Dropdown */}
                    {portfolioItems.length > 0 && (
                        <>
                            <Button
                                className="navbar-nav-btn dropdown-btn"
                                endIcon={<ExpandMoreIcon />}
                                onClick={(e) => setAnalyticsAnchor(e.currentTarget)}
                            >
                                Portfolio
                            </Button>
                            <Menu
                                anchorEl={analyticsAnchor}
                                open={Boolean(analyticsAnchor)}
                                onClose={() => setAnalyticsAnchor(null)}
                                className="navbar-menu"
                            >
                                {portfolioItems.map((item) => (
                                    <MenuItem
                                        key={item.path}
                                        onClick={() => {
                                            navigate(item.path);
                                            setAnalyticsAnchor(null);
                                        }}
                                        className="navbar-menu-item"
                                    >
                                        {item.icon && <span className="menu-icon">{item.icon}</span>}
                                        {item.label}
                                    </MenuItem>
                                ))}
                            </Menu>
                        </>
                    )}

                    {/* Analytics Dropdown */}
                    {analyticsItems.length > 0 && (
                        <>
                            <Button
                                className="navbar-nav-btn dropdown-btn"
                                endIcon={<ExpandMoreIcon />}
                                onClick={(e) => setMoreAnchor(e.currentTarget)}
                            >
                                Analytics
                            </Button>
                            <Menu
                                anchorEl={moreAnchor}
                                open={Boolean(moreAnchor)}
                                onClose={() => setMoreAnchor(null)}
                                className="navbar-menu"
                            >
                                {analyticsItems.map((item) => (
                                    <MenuItem
                                        key={item.path}
                                        onClick={() => {
                                            navigate(item.path);
                                            setMoreAnchor(null);
                                        }}
                                        className="navbar-menu-item"
                                    >
                                        {item.icon && <span className="menu-icon">{item.icon}</span>}
                                        {item.label}
                                    </MenuItem>
                                ))}
                            </Menu>
                        </>
                    )}

                    {/* Admin Dropdown */}
                    {adminItems.length > 0 && (
                        <>
                            <Button
                                className="navbar-nav-btn dropdown-btn"
                                endIcon={<ExpandMoreIcon />}
                                onClick={(e) => setAdminAnchor(e.currentTarget)}
                                sx={{ color: "#ff9800" }}
                            >
                                Admin
                            </Button>
                            <Menu
                                anchorEl={adminAnchor}
                                open={Boolean(adminAnchor)}
                                onClose={() => setAdminAnchor(null)}
                                className="navbar-menu"
                            >
                                {adminItems.map((item) => (
                                    <MenuItem
                                        key={item.path}
                                        onClick={() => {
                                            navigate(item.path);
                                            setAdminAnchor(null);
                                        }}
                                        className="navbar-menu-item"
                                    >
                                        {item.icon && <span className="menu-icon">{item.icon}</span>}
                                        {item.label}
                                    </MenuItem>
                                ))}
                            </Menu>
                        </>
                    )}

                    <Button
                        component={Link}
                        to="/community"
                        className="navbar-nav-btn"
                        startIcon={<GroupIcon />}
                    >
                        Community
                    </Button>
                </Box>

                {/* Search Bar (Desktop) */}
                <Box className="navbar-search-desktop">
                    <SearchBar
                        onResults={(results: any[]) => {
                            console.log("Search results:", results);
                        }}
                    />
                </Box>

                {/* Right Section */}
                <Box className="navbar-right-section">
                    {/* Account & Settings */}
                    <Button
                        component={Link}
                        to="/account"
                        className="navbar-icon-btn"
                        startIcon={<AccountCircleIcon />}
                    >
                        Account
                    </Button>

                    <Button
                        component={Link}
                        to="/settings"
                        className="navbar-icon-btn"
                        startIcon={<SettingsIcon />}
                    >
                        Settings
                    </Button>

                    {/* Logout */}
                    <Button
                        onClick={handleLogout}
                        className="navbar-logout-btn"
                        endIcon={<LogoutIcon />}
                    >
                        Logout
                    </Button>

                    {/* Mobile Menu Button */}
                    <IconButton
                        className="navbar-mobile-toggle"
                        onClick={() => setMobileOpen(!mobileOpen)}
                    >
                        {mobileOpen ? <CloseIcon /> : <MenuIcon />}
                    </IconButton>
                </Box>
            </Toolbar>


            {/* Mobile Menu */}
            {mobileOpen && (
                <Box className="navbar-mobile-menu">
                    <Box className="mobile-menu-content">
                        <Button
                            fullWidth
                            component={Link}
                            to="/dashboard"
                            onClick={() => setMobileOpen(false)}
                            className="mobile-menu-btn"
                            startIcon={<DashboardIcon />}
                        >
                            Dashboard
                        </Button>

                        {tradingItems.length > 0 && (
                            <>
                                <Divider sx={{ my: 1 }} />
                                <Typography className="mobile-menu-section-title">Trading</Typography>
                                {tradingItems.map((item) => (
                                    <Button
                                        key={item.path}
                                        fullWidth
                                        onClick={() => {
                                            navigate(item.path);
                                            setMobileOpen(false);
                                        }}
                                        className="mobile-menu-btn"
                                    >
                                        {item.label}
                                    </Button>
                                ))}
                            </>
                        )}

                        {portfolioItems.length > 0 && (
                            <>
                                <Divider sx={{ my: 1 }} />
                                <Typography className="mobile-menu-section-title">Portfolio</Typography>
                                {portfolioItems.map((item) => (
                                    <Button
                                        key={item.path}
                                        fullWidth
                                        onClick={() => {
                                            navigate(item.path);
                                            setMobileOpen(false);
                                        }}
                                        className="mobile-menu-btn"
                                    >
                                        {item.label}
                                    </Button>
                                ))}
                            </>
                        )}

                        {analyticsItems.length > 0 && (
                            <>
                                <Divider sx={{ my: 1 }} />
                                <Typography className="mobile-menu-section-title">Analytics</Typography>
                                {analyticsItems.map((item) => (
                                    <Button
                                        key={item.path}
                                        fullWidth
                                        onClick={() => {
                                            navigate(item.path);
                                            setMobileOpen(false);
                                        }}
                                        className="mobile-menu-btn"
                                    >
                                        {item.label}
                                    </Button>
                                ))}
                            </>
                        )}

                        {adminItems.length > 0 && (
                            <>
                                <Divider sx={{ my: 1 }} />
                                <Typography className="mobile-menu-section-title">Administration</Typography>
                                {adminItems.map((item) => (
                                    <Button
                                        key={item.path}
                                        fullWidth
                                        onClick={() => {
                                            navigate(item.path);
                                            setMobileOpen(false);
                                        }}
                                        className="mobile-menu-btn"
                                    >
                                        {item.label}
                                    </Button>
                                ))}
                            </>
                        )}

                        <Button
                            fullWidth
                            component={Link}
                            to="/community"
                            onClick={() => setMobileOpen(false)}
                            className="mobile-menu-btn"
                            startIcon={<GroupIcon />}
                        >
                            Community
                        </Button>

                        <Divider sx={{ my: 1 }} />

                        <Button
                            fullWidth
                            component={Link}
                            to="/account"
                            onClick={() => setMobileOpen(false)}
                            className="mobile-menu-btn"
                            startIcon={<AccountCircleIcon />}
                        >
                            Account
                        </Button>

                        <Button
                            fullWidth
                            component={Link}
                            to="/settings"
                            onClick={() => setMobileOpen(false)}
                            className="mobile-menu-btn"
                            startIcon={<SettingsIcon />}
                        >
                            Settings
                        </Button>

                        <Divider sx={{ my: 1 }} />

                        <Button
                            fullWidth
                            onClick={handleLogout}
                            className="mobile-menu-logout-btn"
                            endIcon={<LogoutIcon />}
                        >
                            Logout
                        </Button>
                    </Box>
                </Box>)}
        </AppBar>
    )
}


export default NavBar;
