import { Link } from "react-router-dom"

const VerifyLink = () => {
    return (
        <section>
            <h1>Verify Email</h1>
            <br />
            <p>Please check your email to verify your account.</p>
            <br />
            <h2>Navigation</h2>
            <Link to="/login">Back to Login</Link>
            <br />
            <Link to="/">Home</Link>
        </section>
    )
}

export default VerifyLink
