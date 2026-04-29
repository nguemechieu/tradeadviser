import { Link } from "react-router-dom"

const TradingEditor = () => {
    return (
        <section>
            <h1>Trading Editor</h1>
            <br />
            <p>Advanced trading tools and strategy editor.</p>
            <div className="flexGrow">
                <Link to="/">Home</Link>
            </div>
        </section>
    )
}

export default TradingEditor
