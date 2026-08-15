# Concord Clinical Network -- Reporting & QA Tracker

Concord Clinical Network's pharma clients pay for measured HCP engagement, and a wrong number in a client report is a trust problem, not a rounding error. This project builds the QA checkpoint that catches errors before they ship: a rule-based risk score plus a logistic-regression model (AUC 0.954) concentrating 13.42% of real escalations into its top decile, an 8.27x lift. Analysts work the highest-risk reports first, not after a client finds the error.
