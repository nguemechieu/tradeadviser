import {Card, CardContent, CardHeader} from "@mui/material";


const InvestorRelations = () => {
    return (<Card><CardHeader>
        <div className="investor-relations-container">
            <header className="ir-header">
                <h1>Investor Relations</h1>
                <p>Transparency. Vision. Growth.</p>
            </header>
        </div>
        </CardHeader>
<CardContent>
            <section className="ir-section">
                <h2>Company Overview</h2>
                <p>
                    Sopotek is a multi-service technology and maintenance company dedicated to
                    innovation, sustainability, and delivering value to stakeholders. We aim to
                    redefine how modern homes and businesses approach IT and handyman services.
                </p>
            </section>

            <section className="ir-section">
                <h2>Financial Highlights</h2>
                <ul>
                    <li>Q1 Revenue Growth: 24%</li>
                    <li>Profit Margin: 18%</li>
                    <li>Active Clients: 1,200+</li>
                    <li>Expansion into 3 new states in 2025</li>
                </ul>
            </section>

            <section className="ir-section">
                <h2>Strategic Vision</h2>
                <p>
                    Our 5-year plan includes scaling our service model nationally, integrating
                    AI-driven diagnostics in field services, and building an end-to-end digital
                    experience for customers.
                </p>
            </section>

            <section className="ir-section">
                <h2>Reports & Disclosures</h2>
                <p>
                    We publish quarterly performance reports and annual disclosures to ensure
                    accountability and inform our investors of our trajectory.
                </p>
                <ul>
                    <li><a href="/reports/Q1-2025.pdf">Q1 2025 Report</a></li>
                    <li><a href="/reports/2024-Annual.pdf">2024 Annual Report</a></li>
                </ul>
            </section>

            <section className="ir-section">
                <h2>Contact Investor Relations</h2>
                <p>Email: <a href="mailto:ir@sopotek.com">ir@sopotek.com</a></p>
                <p>Phone: (800) 555-0199</p>
            </section>
</CardContent>
        </Card>

    );
};

export default InvestorRelations;
