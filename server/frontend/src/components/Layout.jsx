import { Outlet, useLocation } from "react-router-dom"
import Navigation from "./Navigation"
import './Layout.css'

const Layout = () => {
    const location = useLocation();
    const isAuthPage = location.pathname === '/login' || location.pathname === '/register' || location.pathname === '/verify-link';

    return (
        <main className="App layout-wrapper">
            {!isAuthPage && <Navigation />}
            <div className="layout-content">
                <Outlet />
            </div>
            {!isAuthPage && (
                <footer className="layout-footer">
                    <div className="footer-content">
                        <p>⚡ TradeAdviser - Intelligent Trading Advisory Platform</p>
                        <p className="footer-links">
                            <a href="https://github.com/nguemechieu/tradeadviser" target="_blank" rel="noopener noreferrer">GitHub</a>
                            <span className="divider">•</span>
                            <a href="/docs/routes">Documentation</a>
                            <span className="divider">•</span>
                            <a href="mailto:support@tradeadviser.com">Support</a>
                        </p>
                    </div>
                </footer>
            )}
        </main>
    )
}

export default Layout
