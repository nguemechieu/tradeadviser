import React from "react";
import "./Header.css";
import NavBar from "./NavBar";

const Header = () => {

    return (
        <header className="App-header">
            {/* Logo Section */}

                <a
                    href="https://localhost:3000/"
                    className="site-title"
                    target="_blank"
                    rel="noopener noreferrer"
                >
                    <img src="/logo192.png" alt="Sopotek Logo" className="logo" />

                </a>
            <NavBar/>



        </header>
    );
};

export default Header;
