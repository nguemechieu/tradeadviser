import React, { useState, useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import useAxiosPrivate from "../hooks/useAxiosPrivate";

interface User {
  id: number;
  username: string;
  email?: string;
  // Add more fields as needed
}

const Users: React.FC = () => {
  const [users, setUsers] = useState<User[]>([]);
  const navigate = useNavigate();
  const location = useLocation();
  const axiosPrivate = useAxiosPrivate();

  useEffect(() => {
    const controller = new AbortController();
    let isMounted = true;

    const fetchUsers = async () => {
      try {
        const response = await axiosPrivate.get("/api/v3/users", {
          signal: controller.signal,
        });
        if (isMounted) setUsers(response.data);
      } catch (err) {
        console.error("Failed to fetch users:", err);
        navigate("/login", { state: { from: location }, replace: true });
      }
    };
    fetchUsers();
    return () => {
      isMounted = false;
      controller.abort();
    };
  }, [axiosPrivate, location, navigate]);

  return (
      <article>
        <h2>Users List</h2>
        {users.length > 0 ? (
            <ul>
              {users.map((user) => (
                  <li key={user.id}>{user.username}</li>
              ))}
            </ul>
        ) : (
            <p>No users to display.</p>
        )}
      </article>
  );
};

export default Users;
