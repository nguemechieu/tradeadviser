import React from "react";
import { Link } from "react-router-dom";


const Editor = () => {
  return (
    <section>
      <h1>Editors </h1>
      <br />
      <p>You must have been assigned an Editor role.</p>
      <div className="flex-grow">
        <Link to="/">Home</Link>
      </div>
    </section>
  );
};

export default Editor;
