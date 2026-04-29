import React from "react";
import "./Sitemap.css"; // Optional: Include styles for this component

const Sitemap = () => {
  return (
    <div className="sitemap">
      <h1>Sitemap</h1>
      <p>
        Explore our website through the links below. Quickly access the sections
        that matter most to you.
      </p>

      <div className="sitemap-sections">
        <h2>Site Sections</h2>
        <ul>
          <li>
            <a href="/home">Home</a>
          </li>
          <li>
            <a href="/about-us">About Us</a>
          </li>
          <li>
            <a href="/src/components/Services">Services</a>
          </li>
          <li>
            <a href="/products">Products</a>
          </li>
          <li>
            <a href="/press-contact">Press Contact</a>
          </li>
          <li>
            <a href="/src/components/Careers">Careers</a>
          </li>
          <li>
            <a href="/privacy-policy">Privacy Policy</a>
          </li>
          <li>
            <a href="/cookie-policy">Cookie Policy</a>
          </li>
          <li>
            <a href="/contact-us">Contact Us</a>
          </li>
        </ul>
      </div>

      <div className="resources">
        <h2>Resources</h2>
        <ul>
          <li>
            <a href="/blog">Blog</a>
          </li>
          <li>
            <a href="/src/components/Faqs">FAQs</a>
          </li>
          <li>
            <a href="/documentation">Documentation</a>
          </li>
          <li>
            <a href="/media-kit">Media Kit</a>
          </li>
          <li>
            <a href="/press-releases">Press Releases</a>
          </li>
          <li>
            <a href="/support">Support</a>
          </li>
        </ul>
      </div>

      <div className="social-media">
        <h2>Follow Us</h2>
        <ul>
          <li>
            <a
              href="https://facebook.com/aipower"
              target="_blank"
              rel="noopener noreferrer"
            >
              Facebook
            </a>
          </li>
          <li>
            <a
              href="https://twitter.com/aipower"
              target="_blank"
              rel="noopener noreferrer"
            >
              Twitter
            </a>
          </li>
          <li>
            <a
              href="https://linkedin.com/company/aipower"
              target="_blank"
              rel="noopener noreferrer"
            >
              LinkedIn
            </a>
          </li>
          <li>
            <a
              href="https://instagram.com/aipower"
              target="_blank"
              rel="noopener noreferrer"
            >
              Instagram
            </a>
          </li>
          <li>
            <a
              href="https://youtube.com/aipower"
              target="_blank"
              rel="noopener noreferrer"
            >
              YouTube
            </a>
          </li>
        </ul>
      </div>
    </div>
  );
};

export default Sitemap;
