import { Card } from "@mui/material";
import React, { useState } from "react";

const FAQComponent = () => {
  const [activeIndex, setActiveIndex] = useState(0);

  const toggleAnswer = (index) => {
    if (activeIndex === index) {
      setActiveIndex(0); // Collapse the answer if it's already open
    } else {
      setActiveIndex(index); // Expand the clicked answer
    }
  };

  const faqs = [
    {
      question: "What is React?",
      answer:
        "React is a JavaScript library for building user interfaces, maintained by Facebook and a community of individual developers and companies.",
    },
    {
      question: "How do I create a component in React?",
      answer:
        "To create a component in React, you define a function that returns JSX (HTML-like syntax), and then you export it to use in other parts of your application.",
    },
    {
      question: "What is JSX?",
      answer:
        "JSX is a syntax extension for JavaScript that looks similar to XML or HTML. It’s used in React to describe the UI structure.",
    },
    {
      question: "What is state in React?",
      answer:
        "State in React is an object that holds data that can change over time. React components can use state to render UI based on the current data.",
    },
  ];

  return (<Card>
    <div className="faq-container">
      <h2>Frequently Asked Questions</h2>
      <div className="faq-list">
        {faqs.map((faq, index) => (
          <div key={index} className="faq-item">
            <div className="faq-question" onClick={() => toggleAnswer(index)}>
              <h3>{faq.question}</h3>
              <span>{activeIndex === index ? "-" : "+"}</span>
            </div>
            {activeIndex === index && (
              <div className="faq-answer">
                <p>{faq.answer}</p>
              </div>
            )}
          </div>
        ))}
      </div>
    </div></Card>
  );
};

export default FAQComponent;
