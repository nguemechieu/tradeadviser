import React, { useEffect, useState } from "react";
import { axiosPublic } from "../api/axios";

const PrivacyPolicy = () => {
  const [policies, setPolicies] = useState({
    terms_of_service: [],
    data_security_policy: [],
    cookie_policy: "",
  });
  const [error, setError] = useState("");

  useEffect(() => {
    const fetchPolicies = async () => {
      try {
        const termsResponse = await axiosPublic.get(
          "./privacy/policy",
        );
        const securityResponse = await axiosPublic.get(
          "[Your Data Security Policy API Endpoint]",
        );
        const cookieResponse = await axiosPublic.get(
          "[Your Cookie Policy API Endpoint]",
        );

        setPolicies({
          terms_of_service: termsResponse.data,
          data_security_policy: securityResponse.data,
          cookie_policy: cookieResponse.data,
        });
      } catch (err) {
        setError(
          JSON.stringify (err?.data)
        )

      }
    };

    fetchPolicies().catch((err) => {
      console.error("Failed to fetch policies:", err);
    });
  }, [error]);

  return (<>
    <div style={{ padding: "20px", fontFamily: "Arial, sans-serif" }}>
      {error && <p style={{ color: "red" }}>Error fetching data: {error}</p>}
      {policies.terms_of_service.length > 0 && (
        <section>
          <h1>Terms of Service</h1>
          <ul>
            {policies.terms_of_service.map((term, index) => (
              <li key={index}>{term}</li>
            ))}
          </ul>
        </section>
      )}
      {policies.data_security_policy.length > 0 && (
        <section>
          <h1>Data Security Policy</h1>
          <ul>
            {policies.data_security_policy.map((policy, index) => (
              <li key={index}>{policy}</li>
            ))}
          </ul>
        </section>
      )}
      {policies.cookie_policy && (
        <section>
          <h1>Cookie Policy</h1>
          <p>{policies.cookie_policy}</p>
        </section>
      )}

      <h1>Privacy Policy</h1>
      <p>
        Effective Date:{" "}
        {
          // Replace it with actual effective date
          "2023-01-01"
        }
      </p>

      <section>
        <h2>Introduction</h2>
        <p>
          Welcome to Sopotek. We value your privacy and are committed to
          protecting your personal information.
        </p>
      </section>

      <section>
        <h2>Information We Collect</h2>
        <p>
          We collect information to provide better services to our users. This
          includes:
        </p>
        <ul>
          <li>
            Personal Identification Information (e.g., name, email address,
            phone number).
          </li>
          <li>
            Usage Data (e.g., IP address, browser type, and pages visited).
          </li>
        </ul>
      </section>

      <section>
        <h2>How We Use Your Information</h2>
        <p>The information we collect is used to:</p>
        <ul>
          <li>Provide, operate, and maintain our services.</li>
          <li>Improve and personalize user experience.</li>
          <li>Communicate with you regarding updates and support.</li>
        </ul>
      </section>

      <section>
        <h2>Sharing Your Information</h2>
        <p>
          We do not sell your personal data. However, we may share information
          with trusted third-party services to support our operations.
        </p>
      </section>

      <section>
        <h2>Your Rights</h2>
        <p>
          You have the right to access, update, or delete your personal
          information. To exercise these rights, please contact us at support@sopotek.com
        </p>
      </section>

      <section>
        <h2>Changes to This Privacy Policy</h2>
        <p>
          We may update this privacy policy from time to time. We encourage you
          to review this page periodically for the latest information.
        </p>
      </section>


        <p>
          If you have any questions, please contact us at support@sopotek.com.
        </p>

    </div></>
  );
};

export default PrivacyPolicy;
