import React from "react";
import {Card} from "@mui/material";

const Footer = () => {
  return (
    <footer><Card>
      <div
        className="text-info"
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: "1rem",
          justifyContent: "center",
        }}
      >

        <a href="/terms-of-service">Terms of Service</a>
        <a href="/privacy-policy">Privacy Policy</a>
        <a href="/cookie-policy">Cookie Policy</a>
        <a href="/src/components/About">About Us</a>
        <a href="/press-contact">Press Contact</a>
        <a href="/src/components/Careers">Careers</a>
        <a href="/press-releases">Press Releases</a>
        <a href="/investor-relations">Investor Relations</a>
        <a href="/affiliate-program">Affiliate Program</a>
        <a href="/components/Faqs">FAQs</a>
        <a href="/components/Sitemap">Sitemap</a>
        <a href="/components/Security">Security</a>
      </div>
    </Card>
        <p>
            © 2023 - {new Date().getFullYear()} Sopotek ,Inc. All rights
            reserved.</p>
    </footer>
  );
};

export default Footer;
