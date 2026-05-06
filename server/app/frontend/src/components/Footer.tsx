import React from "react";
import { Box, Container, Grid, Typography, Link, Divider } from "@mui/material";
import LinkedInIcon from "@mui/icons-material/LinkedIn";
import TwitterIcon from "@mui/icons-material/Twitter";
import GitHubIcon from "@mui/icons-material/GitHub";
import EmailIcon from "@mui/icons-material/Email";
import "./Footer.css";

const Footer = () => {
    const currentYear = new Date().getFullYear();

    const footerSections = {
        product: {
            title: "Product",
            links: [
                { label: "Trading Editor", href: "/trading-editor" },
                { label: "Portfolio", href: "/portfolio" },
                { label: "Signals", href: "/signals" },
                { label: "Risk Management", href: "/risk" },
            ],
        },
        company: {
            title: "Company",
            links: [
                { label: "About Us", href: "/about" },
                { label: "Careers", href: "/careers" },
                { label: "Press Releases", href: "/press-releases" },
                { label: "Investor Relations", href: "/investor-relations" },
            ],
        },
        resources: {
            title: "Resources",
            links: [
                { label: "Documentation", href: "/docs/guide" },
                { label: "API Routes", href: "/docs/routes" },
                { label: "FAQ", href: "/faqs" },
                { label: "Community", href: "/community" },
            ],
        },
        legal: {
            title: "Legal",
            links: [
                { label: "Terms of Service", href: "/terms-of-service" },
                { label: "Privacy Policy", href: "/privacy-policy" },
                { label: "Cookie Policy", href: "/cookie-policy" },
                { label: "Security", href: "/security" },
            ],
        },
    };

    const socialLinks = [
        { icon: LinkedInIcon, href: "https://linkedin.com", label: "LinkedIn" },
        { icon: TwitterIcon, href: "https://twitter.com", label: "Twitter" },
        { icon: GitHubIcon, href: "https://github.com/tradeadviser", label: "GitHub" },
        { icon: EmailIcon, href: "mailto:contact@tradeadviser.com", label: "Email" },
    ];

    return (
        <footer className="footer-container">
            <Container maxWidth="lg">
                {/* Main Footer Content */}
                <Box className="footer-content">
                    <Grid container spacing={4} className="footer-grid">
                        {/* Logo & Description */}
                        <Grid item xs={12} sm={6} md={3} className="footer-section">
                            <Box className="footer-logo-section">
                                <Typography variant="h6" className="footer-title">
                                    🚀 TradeAdviser
                                </Typography>
                                <Typography variant="body2" className="footer-description">
                                    Intelligent Trading Advisory Platform with AI-powered agents and real-time analytics.
                                </Typography>
                                {/* Social Links */}
                                <Box className="footer-social">
                                    {socialLinks.map((social) => {
                                        const IconComponent = social.icon;
                                        return (
                                            <Link
                                                key={social.label}
                                                href={social.href}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className="social-link"
                                                aria-label={social.label}
                                            >
                                                <IconComponent fontSize="small" />
                                            </Link>
                                        );
                                    })}
                                </Box>
                            </Box>
                        </Grid>

                        {/* Product Links */}
                        <Grid item xs={12} sm={6} md={2} className="footer-section">
                            <Typography variant="h6" className="footer-section-title">
                                {footerSections.product.title}
                            </Typography>
                            <Box className="footer-links">
                                {footerSections.product.links.map((link) => (
                                    <Link
                                        key={link.href}
                                        href={link.href}
                                        className="footer-link"
                                    >
                                        {link.label}
                                    </Link>
                                ))}
                            </Box>
                        </Grid>

                        {/* Company Links */}
                        <Grid item xs={12} sm={6} md={2} className="footer-section">
                            <Typography variant="h6" className="footer-section-title">
                                {footerSections.company.title}
                            </Typography>
                            <Box className="footer-links">
                                {footerSections.company.links.map((link) => (
                                    <Link
                                        key={link.href}
                                        href={link.href}
                                        className="footer-link"
                                    >
                                        {link.label}
                                    </Link>
                                ))}
                            </Box>
                        </Grid>

                        {/* Resources Links */}
                        <Grid item xs={12} sm={6} md={2} className="footer-section">
                            <Typography variant="h6" className="footer-section-title">
                                {footerSections.resources.title}
                            </Typography>
                            <Box className="footer-links">
                                {footerSections.resources.links.map((link) => (
                                    <Link
                                        key={link.href}
                                        href={link.href}
                                        className="footer-link"
                                    >
                                        {link.label}
                                    </Link>
                                ))}
                            </Box>
                        </Grid>

                        {/* Legal Links */}
                        <Grid item xs={12} sm={6} md={2} className="footer-section">
                            <Typography variant="h6" className="footer-section-title">
                                {footerSections.legal.title}
                            </Typography>
                            <Box className="footer-links">
                                {footerSections.legal.links.map((link) => (
                                    <Link
                                        key={link.href}
                                        href={link.href}
                                        className="footer-link"
                                    >
                                        {link.label}
                                    </Link>
                                ))}
                            </Box>
                        </Grid>
                    </Grid>

                    {/* Divider */}
                    <Divider className="footer-divider" />

                    {/* Footer Bottom */}
                    <Box className="footer-bottom">
                        <Typography variant="body2" className="footer-copyright">
                            © {currentYear} TradeAdviser, Inc. All rights reserved.
                        </Typography>
                        <Typography variant="body2" className="footer-tagline">
                            Built with ❤️ for traders, by traders.
                        </Typography>
                    </Box>
                </Box>
            </Container>
        </footer>
    );
};

export default Footer;
