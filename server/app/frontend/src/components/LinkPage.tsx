import React from "react";
import { Link } from "react-router-dom";
import {Card, CardContent} from "@mui/material";
const LinkPage = () => {
  return (
    <Card>
      <h1>Links </h1>
      <br />
      <h2>Public</h2>

        <CardContent>

      <Link to="/about">About </Link>
      <Link to="/contact">Contact </Link>
      <Link to="/terms">Terms </Link>
      <Link to="/privacy">Privacy Policy </Link>
      <Link to="/support">Support </Link>
      <Link to="/faq">FAQ </Link>
      <Link to="/blog">Blog </Link>
      <Link to="/podcast">Podcast </Link>
      <Link to="/events">Events </Link>
      <br />
        </CardContent>
      <h2>Private </h2>
        <div className="flex-grow">
      <Link to="/">Home </Link>
      <Link to="/editor">Editor </Link>
      <Link to="/admin">Admin </Link>


        <Link to="/profile">Profile </Link>

        <Link to="/dashboard">Dashboard </Link>
      <Link to="/settings">Settings </Link>
      <Link to="/market">Market</Link>
      <Link to="/settings">Settings </Link>
      <Link to="/market">Market </Link>
      <Link to="/account">Account </Link>
      <Link to="/positions">Positions </Link>
      <Link to="/watchlist">Watchlist </Link>
      <Link to="/orders">Orders </Link>
      <Link to="/analysis">Analysis </Link>
      <Link to="/trade">Trade </Link>
      <Link to="/notifications">Notifications </Link>
      <Link to="/messages">Messages </Link>
      <Link to="/wallet">Wallet </Link>
      <Link to="/news">News </Link>
      <Link to="/music">Music </Link>
      <Link to="/videos">Videos </Link>
      <Link to="/crypto">Crypto </Link>
      <Link to="/chat">Chat </Link>
      <Link to="/telegram">Telegram</Link>
      <Link to="/discord">Discord </Link>
      <Link to="/exchanges">Exchanges </Link>
        <Link to="/employee">Employee </Link>
        </div>
    </Card>
  );
};

export default LinkPage;
