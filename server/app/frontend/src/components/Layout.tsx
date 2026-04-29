
import { Outlet } from "react-router-dom";
import Header from "./Header";
import Footer from "./Footer";
import "./Layout.css";

const Layout = () => {
  return (
        <>
            <Header />
<main className="main">
        <Outlet />
</main>
            <Footer />
    </>
  );
};

export default Layout;
