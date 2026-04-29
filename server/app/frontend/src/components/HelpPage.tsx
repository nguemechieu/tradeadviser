import React from "react";
import {
  Box,
  Container,
  Typography,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Button,
  Grid,
  Card,
  CardContent,
} from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";

const HelpPage = () => {
  const faqs = [
    {
      question: "How do I reset my password?",
      answer:
        "You can reset your password by going to the login page and clicking on 'Forgot Password'. Follow the instructions sent to your registered email.",
    },
    {
      question: "How do I update my profile?",
      answer:
        "Go to the 'Profile' page from the menu, where you can update your personal information and profile picture.",
    },
    {
      question: "What should I do if I encounter an error?",
      answer:
        "Please contact our support team with a detailed description of the issue, including any error messages you received.",
    },
    {
      question: "How do I contact customer support?",
      answer:
        "You can contact customer support by email at support@example.com or by using the 'Contact Us' form below.",
    },
  ];

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
      {/* Page Header */}
      <Typography variant="h4" gutterBottom>
        Help & Support
      </Typography>
      <Typography variant="body1" gutterBottom>
        Find answers to common questions or reach out to our support team for
        assistance.
      </Typography>

      {/* FAQs Section */}
      <Box sx={{ mt: 4 }}>
        <Typography variant="h5" gutterBottom>
          Frequently Asked Questions
        </Typography>
        {faqs.map((faq, index) => (
          <Accordion key={index}>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography>{faq.question}</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Typography>{faq.answer}</Typography>
            </AccordionDetails>
          </Accordion>
        ))}
      </Box>

      {/* Contact Section */}
      <Box sx={{ mt: 6 }}>
        <Typography variant="h5" gutterBottom>
          Need More Help?
        </Typography>
        <Grid container spacing={4}>
          <Card>
            <CardContent>
              <Typography variant="h6">Contact Support</Typography>
              <Typography variant="body2">
                If you need further assistance, please reach out to our support
                team.
              </Typography>
              <Button
                variant="contained"
                color="primary"
                sx={{ mt: 2 }}
                href="mailto:support@sopotek.com"
              >
                Email Support
              </Button>
            </CardContent>
          </Card>
          <Card>
            <CardContent>
              <Typography variant="h6">Documentation</Typography>
              <Typography variant="body2">
                Visit our documentation page for detailed guides and resources.
              </Typography>
              <Button
                variant="contained"
                color="secondary"
                sx={{ mt: 2 }}
                href="/documentation"
              >
                View Documentation
              </Button>
            </CardContent>
          </Card>
        </Grid>
      </Box>

      {/* Footer Section */}
      <Box sx={{ mt: 6, textAlign: "center" }}>
        <Typography variant="body2" color="textSecondary">
          © {new Date().getFullYear()} Your Company. All rights reserved.
        </Typography>
      </Box>
    </Container>
  );
};

export default HelpPage;
