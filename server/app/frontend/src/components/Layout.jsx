import { Outlet } from "react-router-dom"
import '../styles.css'

const Layout = () => {
    return (
        <main className="App" style={{ minHeight: '100vh', width: '100%', display: 'flex', flexDirection: 'column' }}>
            <div style={{ flex: 1 }}>
                <Outlet />
            </div>
            <footer style={{
                textAlign: 'center',
                padding: '2rem 1rem',
                borderTop: '1px solid rgba(136, 168, 203, 0.2)',
                color: '#8ea3bc',
                fontSize: '0.9rem',
                backgroundColor: 'rgba(15, 23, 42, 0.5)'
            }}>
                <p>⚡ Powered by AI</p>
            </footer>
        </main>
    )
}

export default Layout
