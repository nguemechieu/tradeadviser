import React, { useEffect, useState } from 'react';
import {axiosPrivate} from "../api/axiosPrivate";


const UserProfile = () => {
    const [userInfo, setUserInfo] = useState(null);

    useEffect(() => {  const code = new URLSearchParams(window.location.search).get('code');
        // Retrieve user information from your backend
        const fetchUserInfo = async () => {
            const response = await axiosPrivate.post('/api/v3/auth/google/callback?code=' + new URLSearchParams(window.location.search).get('code'),
                {
                    code: code
                });
            const data = await response.data
            setUserInfo(data);
        };


        if (code) {
            fetchUserInfo().then(r => {
                console.log(r);
            });
        }
    }, []);

    if (!userInfo) return <div>Loading...</div>;

    return (
        <div>
            <h1>User Profile</h1>
            <p>Name: {userInfo}</p>

        </div>
    );
};

export default UserProfile;
