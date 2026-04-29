import React from "react";
import {Card, CardContent} from "@mui/material";

const CookiePolicy = () => {
  return (<Card><CardContent>
    <div style={{ padding: "20px", fontFamily: "Arial, sans-serif" }}>
      <h1 style={{ textAlign: "center" }}>Cookie Policy</h1>

      <p>
        At  Sopotek, Inc, we use cookies and similar technologies to enhance your
        experience on our website, provide you with personalized content, and
        analyze site traffic. This Cookie Policy explains what cookies are, how
        we use them, and your choices regarding their use.
      </p>

      <h2>What Are Cookies?</h2>
      <p>
        Cookies are small text files that are stored on your device (computer,
        tablet, or mobile) when you visit a website. They help websites function
        properly and provide information to website owners to enhance user
        experience.
      </p>

      <h2>Types of Cookies We Use</h2>
      <ul>
        <li>
          <strong>Essential Cookies:</strong> These cookies are necessary for
          the website to function and cannot be switched off in our systems.
          They are usually set in response to actions you take, such as logging
          in or filling out forms.
        </li>
        <li>
          <strong>Performance Cookies:</strong> These cookies help us understand
          how visitors interact with our website by collecting and reporting
          information anonymously.
        </li>
        <li>
          <strong>Functional Cookies:</strong> These cookies enable the website
          to provide enhanced functionality and personalization. They may be set
          by us or third-party providers whose services we use.
        </li>
        <li>
          <strong>Advertising Cookies:</strong> These cookies track your online
          activity to help us deliver more relevant advertising or limit the
          number of times you see an ad.
        </li>
      </ul>

      <h2>How We Use Cookies</h2>
      <p>
        We use cookies to:
        <ul>
          <li>Remember your preferences and settings.</li>
          <li>Analyze website traffic and improve site performance.</li>
          <li>Deliver personalized content and advertisements.</li>
        </ul>
      </p>

      <h2>Your Choices</h2>
      <p>
        You can control and manage cookies through your browser settings. Most
        browsers allow you to refuse or delete cookies. Please note that
        disabling cookies may affect the functionality of our website.
      </p>

      <h2>Third-Party Cookies</h2>
      <p>
        Some cookies may be placed by third-party services we use, such as
        analytics or advertising providers. These third parties have their own
        privacy and cookie policies, which we encourage you to review.
      </p>

      <h2>Updates to This Policy</h2>
      <p>
        We may update this Cookie Policy from time to time to reflect changes in
        our practices or for other operational, legal, or regulatory reasons.
        Please revisit this page periodically to stay informed about our use of
        cookies.
      </p>

      <h2>Contact Us</h2>
      <p>
        If you have any questions about this Cookie Policy, please contact us at{" "}
        <a href="mailto:privacy@sopotek.com">privacy@sopotek.com</a>
        .
      </p>
    </div></CardContent></Card>
  );
};

export default CookiePolicy;
