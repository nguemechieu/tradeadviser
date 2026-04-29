import React, { useState } from "react";

const Chat = () => {
  const [messages, setMessages] = useState([
    { id: 1, text: "Hey there!", sender: "friend" },
    { id: 2, text: "Hi! How's it going?", sender: "user" },
  ]);

  const [contacts] = useState([
    {
      id: 1,
      name: "Alice Smith",
      profilePicture: "https://via.placeholder.com/40",
    },
    {
      id: 2,
      name: "Bob Johnson",
      profilePicture: "https://via.placeholder.com/40",
    },
    {
      id: 3,
      name: "Charlie Brown",
      profilePicture: "https://via.placeholder.com/40",
    },
  ]);

  const [newMessage, setNewMessage] = useState("");

  const handleSendMessage = () => {
    if (newMessage.trim() === "") return;

    setMessages((prevMessages) => [
      ...prevMessages,
      { id: Date.now(), text: newMessage, sender: "user" },
    ]);

    setNewMessage("");
  };

  return (
    <div className="facebook-chat">
      {/* Sidebar */}
      <div className="chat-sidebar">
        <h3>Contacts</h3>
        <ul className="contact-list">
          {contacts.map((contact) => (
            <li key={contact.id} className="contact-item">
              <img src={contact.profilePicture} alt={contact.name} />
              <span>{contact.name}</span>
            </li>
          ))}
        </ul>
      </div>

      {/* Chat Area */}
      <div className="chat-area">
        <div className="chat-header">
          <h3>Chat</h3>
        </div>
        <div className="chat-messages">
          {messages.map((message) => (
            <div
              key={message.id}
              className={`chat-message ${
                message.sender === "user" ? "user-message" : "friend-message"
              }`}
            >
              {message.text}
            </div>
          ))}
        </div>
        <div className="chat-input">
          <input
            type="text"
            placeholder="Type a message..."
            value={newMessage}
            onChange={(e) => setNewMessage(e.target.value)}
          />
          <button onClick={handleSendMessage}>Send</button>
        </div>
      </div>
    </div>
  );
};

export default Chat;
