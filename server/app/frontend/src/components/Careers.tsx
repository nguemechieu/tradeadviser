import React, { useState } from "react";

const Careers = () => {
  const [activeJob, setActiveJob] = useState(0);

  const toggleJobDetails = (index) => {
    if (activeJob === index) {
      setActiveJob(0); // Collapse the details if it's already open
    } else {
      setActiveJob(index); // Show the clicked job's details
    }
  };

  const jobs = [
    {
      title: "Software Engineer",
      location: "New York, NY",
      description:
        "Develop and maintain web applications using modern technologies.",
      fullDescription:
        "We are looking for a talented Software Engineer to join our development team. You will work on building scalable applications, writing high-quality code, and collaborating with other team members. Requirements include experience with JavaScript, React, Node.js, and database management.",
    },
    {
      title: "Product Manager",
      location: "San Francisco, CA",
      description: "Lead product development from ideation to launch.",
      fullDescription:
        "As a Product Manager, you will be responsible for defining product vision, collaborating with cross-functional teams, and ensuring that product features meet customer needs. You should have a strong background in product strategy, roadmapping, and agile development.",
    },
    {
      title: "UX Designer",
      location: "Remote",
      description: "Create user-centered designs and improve user experiences.",
      fullDescription:
        "We are seeking a creative UX Designer who can transform complex ideas into intuitive and attractive interfaces. You will work closely with developers and product managers to create designs that meet user needs and business goals. Proficiency in wireframing, prototyping, and user research is required.",
    },
  ];

  return (
    <div className="careers-container">
      <h2>Join Our Team</h2>
      <div className="job-list">
        {jobs.map((job, index) => (
          <div key={index} className="job-item">
            <div className="job-header" onClick={() => toggleJobDetails(index)}>
              <h3>{job.title}</h3>
              <span>{job.location}</span>
            </div>
            <div className="job-description">
              <p>{job.description}</p>
              <button onClick={() => toggleJobDetails(index)}>
                {activeJob === index ? "Hide Details" : "View Details"}
              </button>
            </div>
            {activeJob === index && (
              <div className="job-details">
                <p>{job.fullDescription}</p>
                <button className="apply-button">Apply Now</button>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

export default Careers;
