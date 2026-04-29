import React from "react";
import { Card, CardContent } from "@mui/material";
import { Link } from "react-router-dom";

const Missing = () => {
    return (<>
        <Card sx={{ margin: 4 }}>
            <CardContent>
                <div
                    style={{
                        display: "flex",
                        flexDirection: "column",
                        justifyContent: "center",
                        alignItems: "center",
                        minHeight: "80vh",
                        textAlign: "center",
                        padding: "20px",
                    }}
                >
                    {/* Not Found Image */}
                    <img
                        src="../../public/notfound.png"
                        alt="404 Not Found"
                        style={{ maxWidth: "300px", marginBottom: "1rem" }}
                    />

                    {/* Text */}
                    <h2>Oops!</h2>
                    <p style={{ fontSize: "1.2rem", marginBottom: "1.5rem" }}>
                        We can't find the page you're looking for.
                    </p>

                    {/* Homepage Button */}
                    <Link
                        to="/"
                        style={{
                            padding: "0.8rem 1.5rem",
                            fontSize: "1rem",
                            fontWeight: "bold",
                            color: "#fff",
                            backgroundColor: "#1976d2",
                            borderRadius: "5px",
                            textDecoration: "none",
                        }}
                    >
                        Go to Homepage
                    </Link>
                </div>
            </CardContent>
        </Card>
    </> );
};

export default Missing;
