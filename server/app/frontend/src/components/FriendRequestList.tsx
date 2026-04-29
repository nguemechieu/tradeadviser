import React from "react";

const FriendRequestList = ({ requests, onAccept, onReject }) => (
  <div>
    <h3>Friend </h3>
    <ul style={{ listStyleType: "none", padding: 0 }}>
      {requests.map(
        (request: { id: React.Key; name: string | number | bigint | boolean | React.ReactElement<unknown, string | React.JSXElementConstructor<any>> | Iterable<React.ReactNode> | React.ReactPortal | Promise<string | number | bigint | boolean | React.ReactPortal | React.ReactElement<unknown, string | React.JSXElementConstructor<any>> | Iterable<React.ReactNode>>; status: string | number | bigint | boolean | React.ReactElement<unknown, string | React.JSXElementConstructor<any>> | Iterable<React.ReactNode> | React.ReactPortal | Promise<string | number | bigint | boolean | React.ReactPortal | React.ReactElement<unknown, string | React.JSXElementConstructor<any>> | Iterable<React.ReactNode>>; }) => (
          <li
            key={request.id}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              marginBottom: "10px",
              border: "1px solid #ddd",
              padding: "10px",
              borderRadius: "5px",
            }}
          >
            <div>
              <strong>{request.name}</strong>
              <p>{request.status}</p>
            </div>
            <div>
              <button onClick={() => onAccept(request.id)}>Accept</button>
              <button onClick={() => onReject(request.id)}>Reject</button>
              <button onClick={() => onAccept(request.id)}>Delete</button>
            </div>
          </li>
        ),
      )}
    </ul>
  </div>
);

export default FriendRequestList;
