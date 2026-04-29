import { Link } from "react-router-dom"

const Community = () => {
    return (
        <section>
            <h1>Community</h1>
            <br />
            <p>Community features and discussions for traders.</p>
            <div className="flexGrow">
                <Link to="/">Home</Link>
            </div>
        </section>
    )
}

export default Community
