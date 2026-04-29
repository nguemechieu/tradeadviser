import  { useState } from "react";

const OrderPanel = () => {
  const [orderType, setOrderType] = useState("Buy");
  const [quantity, setQuantity] = useState("");
  const [price, setPrice] = useState("");

  const handleOrderSubmit = () => {
    alert(`Order Placed: ${orderType} ${quantity} at $${price}`);
    // Add an API call to place an order
  };

  return (
    <div style={{ padding: "10px", border: "1px solid #ccc" }}>
      <h3>Order Panel</h3>
      <select
        value={orderType}
        onChange={(e) => setOrderType(e.target.value)}
        style={{ marginBottom: "10px" }}
      >
        <option value="Buy">Buy</option>
        <option value="Sell">Sell</option>
      </select>
      <div>
        <label>Quantity:</label>
        <input
          type="number"
          value={quantity}
          onChange={(e) => setQuantity(e.target.value)}
        />
      </div>
      <div>
        <label>Price:</label>
        <input
          type="number"
          value={price}
          onChange={(e) => setPrice(e.target.value)}
        />
      </div>
      <button onClick={handleOrderSubmit}>Place Order</button>
    </div>
  );
};

export default OrderPanel;
