import React, { useState, useEffect } from "react";

import FriendRequestList from "./FriendRequestList";
import {axiosPrivate} from "../api/axiosPrivate";

const FriendsPage = () => {
  const [requests, setRequests] = useState([]);


  useEffect(() => {
    // Mock API call to fetch friends
    // Mock API call to fetch friend requests
      const fetchRequests = async () => {
        try {
          const response = await axiosPrivate.get("/api/friend-requests");
          setRequests(response.data);
        } catch (error) {
          console.error("Error fetching friend requests: ", error);
        }
      };
      fetchRequests().catch((error) =>
        console.error("Error fetching friend requests: ", error),
      );

    fetchRequests().then(() => console.log("Friend data fetched"));
  }, []);
  const handleAcceptRequest = (id) => {
    alert(`Accepted friend request from ${id}`);
    setRequests(requests.filter((request) => request.id !== id));
  };

  const handleRejectRequest = (id) => {
    alert(`Rejected friend request from ${id}`);
    setRequests(requests.filter((request) => request.id !== id));
  };
  const [friends, setFriends] = useState([]);
  useEffect(() => {
    const fetchFriends = async () => {
      try {
        const response = await axiosPrivate.get("/api/v3/friends");
        setFriends(response.data);
      } catch (error) {
        console.error("Error fetching friends: ", error);
      }
    };
    fetchFriends().catch((error) =>
      console.error("Error fetching friends: ", error),
    );
  }, [friends]);

  return (
    <div
      style={{
        padding: "20px",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
      }}
    >
      <h2>Friends Page</h2>

      <FriendRequestList
        requests={requests}
        onAccept={handleAcceptRequest}
        onReject={handleRejectRequest}
      />
    </div>
  );
};

export default FriendsPage;
