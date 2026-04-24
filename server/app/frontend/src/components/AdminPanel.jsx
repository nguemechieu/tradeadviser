import { Link } from "react-router-dom";
import { UsersLicensesDashboard } from './users_licenses';

const AdminPanel = () => {
    return (
        <section>
            <h1>User & License Management</h1>
            <br />
            <UsersLicensesDashboard token={localStorage.getItem('token')} onError={() => {}} />
            <br />
            <div className="flexGrow">
                <Link to="/">Home</Link>
            </div>
        </section>
    )
}

export default AdminPanel
